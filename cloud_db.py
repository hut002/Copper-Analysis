"""Persistent PostgreSQL storage. Uses authenticated user id for isolation."""
import json, os
from contextlib import contextmanager
import pandas as pd

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id BIGSERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE,
 password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS login_attempts (
 username TEXT PRIMARY KEY, failures INT NOT NULL DEFAULT 0,
 last_failed TIMESTAMPTZ, locked_until TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS accounts (
 user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 market TEXT NOT NULL, mode TEXT NOT NULL,
 cash DOUBLE PRECISION NOT NULL, initial_cash DOUBLE PRECISION NOT NULL,
 qty INTEGER NOT NULL DEFAULT 0, avg_price DOUBLE PRECISION NOT NULL DEFAULT 0,
 realized DOUBLE PRECISION NOT NULL DEFAULT 0, day_idx INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(user_id,market,mode)
);
CREATE TABLE IF NOT EXISTS orders (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 market TEXT NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL,
 side TEXT NOT NULL, lots INTEGER NOT NULL, order_type TEXT NOT NULL,
 limit_price DOUBLE PRECISION, status TEXT NOT NULL, submitted_price DOUBLE PRECISION,
 executed_at TEXT, executed_price DOUBLE PRECISION, reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_user_market ON orders(user_id,market,mode,id);
CREATE TABLE IF NOT EXISTS valuations (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 market TEXT NOT NULL, mode TEXT NOT NULL,
 observation_date TEXT, price DOUBLE PRECISION, cash DOUBLE PRECISION,
 qty INTEGER, equity DOUBLE PRECISION, margin DOUBLE PRECISION, recorded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_vals_user_market ON valuations(user_id,market,mode,id);
CREATE TABLE IF NOT EXISTS market_cache (
 user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 market TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL,
 saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,market)
);
'''

class DatabaseConfigError(RuntimeError):
    """Sanitized database configuration error, safe to show to signed-out users."""


class DatabaseConnectionError(RuntimeError):
    """Sanitized connection error: never includes a URL, username or password."""


def _secret_value(name, default=None):
    """Load Streamlit secrets in cloud, environment variables in CLI tools."""
    value = os.environ.get(name)
    if value is not None and value != "":
        return value
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError, AttributeError):
        return default


def connection_options(url=None):
    """Prefer separate parameters; avoids percent-encoding passwords in DSN URLs.

    Cloud secrets example: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
    DATABASE_URL remains supported for backward compatibility.
    """
    if url:
        return {'conninfo': str(url), 'sslmode': 'require'}
    host = _secret_value('DB_HOST')
    user = _secret_value('DB_USER')
    password = _secret_value('DB_PASSWORD')
    if host or user or password:
        if not all((host, user, password)):
            raise DatabaseConfigError('DB_CONFIG: DB_HOST / DB_USER / DB_PASSWORD must all be provided')
        port = _secret_value('DB_PORT', 5432)
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise DatabaseConfigError('DB_CONFIG: DB_PORT must be numeric') from None
        if not 1 <= port <= 65535:
            raise DatabaseConfigError('DB_CONFIG: invalid DB_PORT')
        return {'host': str(host).strip(), 'port': port,
                'dbname': str(_secret_value('DB_NAME', 'postgres')),
                'user': str(user), 'password': str(password), 'sslmode': 'require'}
    dsn = _secret_value('DATABASE_URL')
    if not dsn:
        raise DatabaseConfigError('DB_CONFIG: configure DB_HOST/DB_USER/DB_PASSWORD or DATABASE_URL in Streamlit Secrets')
    if '[YOUR-PASSWORD]' in str(dsn) or 'YOUR_PASSWORD' in str(dsn):
        raise DatabaseConfigError('DB_CONFIG: placeholder database password is still present')
    return {'conninfo': str(dsn), 'sslmode': 'require'}


def classify_connection_error(error):
    """Return a safe error category without logging confidential DSNs."""
    msg = str(error).lower()
    if any(x in msg for x in ('password authentication failed', 'authentication failed', 'invalid password', '28p01')):
        return 'DB_AUTH: incorrect PostgreSQL username or password'
    if any(x in msg for x in ('tenant or user not found', 'unknown tenant', 'invalid tenant')):
        return 'DB_POOLER_USER: verify pooler user and project reference'
    if any(x in msg for x in ('could not translate host name', 'name or service not known', 'nodename nor servname', 'temporary failure in name resolution')):
        return 'DB_DNS: verify database host and DNS'
    if any(x in msg for x in ('timed out', 'timeout', 'connection timeout')):
        return 'DB_TIMEOUT: database not reachable within 12 seconds'
    if any(x in msg for x in ('certificate', 'ssl error', 'tls error', 'ssl connection')):
        return 'DB_TLS: check pooler TLS and certificate/network configuration'
    if any(x in msg for x in ('connection refused', 'no route to host', 'network is unreachable')):
        return 'DB_NETWORK: host/port/network access failed'
    if any(x in msg for x in ('permission denied', 'insufficient privilege', '42501')):
        return 'DB_PERMISSION: database account lacks schema privileges'
    if any(x in msg for x in ('database', 'does not exist', '3d000')) and ('does not exist' in msg):
        return 'DB_NAME: database does not exist'
    return 'DB_CONNECTION: PostgreSQL connection failed; consult server-side sanitized diagnostics'


def connect(url=None):
    import psycopg
    from psycopg.rows import dict_row
    opts = connection_options(url)
    try:
        return psycopg.connect(**opts, row_factory=dict_row, connect_timeout=12, autocommit=False)
    except psycopg.OperationalError as exc:
        raise DatabaseConnectionError(classify_connection_error(exc)) from None


def init_db(url=None):
    with connect(url) as c:
        for stmt in SCHEMA.split(';'):
            if stmt.strip(): c.execute(stmt)
        c.commit()

def cache_save(user_id,market,df,source):
    payload=df.to_json(orient='records',date_format='iso')
    with connect() as c:
        c.execute('''INSERT INTO market_cache(user_id,market,source,payload) VALUES(%s,%s,%s,%s)
                  ON CONFLICT(user_id,market) DO UPDATE SET source=excluded.source,
                  payload=excluded.payload,saved_at=now()''',(user_id,market,source,payload))
        c.commit()

def cache_load(user_id,market):
    from io import StringIO
    with connect() as c:
        r=c.execute('SELECT source,payload FROM market_cache WHERE user_id=%s AND market=%s',(user_id,market)).fetchone()
    if not r: raise FileNotFoundError('No persistent cached data. Download or upload CSV first.')
    df=pd.read_json(StringIO(r['payload']),orient='records')
    return df,r['source']
