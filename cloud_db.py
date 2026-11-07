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

def connect(url=None):
    import psycopg
    from psycopg.rows import dict_row
    if not url:
        import streamlit as st
        url=st.secrets['DATABASE_URL']
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=12, autocommit=False)

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
