"""Credential-safe diagnosis for Copper Quant PostgreSQL connection failures.
No DSN, usernames, hostnames or raw exceptions are printed.
"""
import re


def classify_database_error(exc):
    parts = []
    current = exc
    for _ in range(3):
        if current is None: break
        parts.append(str(current).lower())
        current = current.__cause__ or current.__context__
    detail = ' | '.join(parts)
    sqlstate = getattr(exc, 'sqlstate', None)
    if sqlstate == '28P01' or 'password authentication failed' in detail:
        return 'DB_AUTH', 'Database password or username rejected. Check Supabase password and the Session Pooler user (postgres.<project-ref>).'
    if 'tenant or user not found' in detail or 'invalid user' in detail:
        return 'DB_POOLER_USER', 'Session Pooler username or project reference is incorrect.'
    if sqlstate in ('28000',) or 'no pg_hba.conf entry' in detail:
        return 'DB_ACCESS', 'Database rejected access. Verify Pooler connection type and SSL requirements.'
    if any(k in detail for k in ('could not translate host name','name or service not known','nodename nor servname','getaddrinfo failed','temporary failure in name resolution')):
        return 'DB_DNS', 'The database hostname could not be resolved. Copy the hostname from Supabase Connect.'
    if any(k in detail for k in ('connection timed out','timed out','timeout expired','operation timed out')):
        return 'DB_TIMEOUT', 'Connection timed out. Verify the Session Pooler host/port, project availability and network.'
    if any(k in detail for k in ('connection refused','actively refused')):
        return 'DB_REFUSED', 'Connection refused by the database endpoint. Verify host and port.'
    if any(k in detail for k in ('ssl','certificate verify failed','tls')):
        return 'DB_TLS', 'TLS/SSL handshake or certificate validation failed. Check SSL connection options.'
    if any(k in detail for k in ('invalid connection option','invalid connection string','invalid port','invalid integer value','could not parse')):
        return 'DB_URL', 'Database URI has invalid syntax. Check percent-encoding of password special characters.'
    if sqlstate == '42501' or 'permission denied' in detail:
        return 'DB_PERMISSION', 'Database role lacks permission to initialize tables.'
    return 'DB_OTHER', 'A database operation failed. Verify a working Session Pooler URI and check Supabase database status.'


def validate_url_shape(url):
    from urllib.parse import urlsplit
    if not url or not isinstance(url,str):
        return 'DB_SECRET_MISSING', 'DATABASE_URL is missing or empty in Streamlit app Secrets.'
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in ('postgresql','postgres') or not parsed.hostname or not parsed.username or not parsed.path:
            return 'DB_URL', 'DATABASE_URL must be a complete postgresql:// URI.'
        if parsed.password is None:
            return 'DB_URL', 'DATABASE_URL contains no password.'
        if parsed.port is None:
            return 'DB_URL', 'DATABASE_URL contains no port; expected 5432 for Supabase Session Pooler.'
        if parsed.hostname.endswith('.pooler.supabase.com') and not parsed.username.startswith('postgres.'):
            return 'DB_POOLER_USER', 'Session Pooler normally requires username postgres.<project-ref>.'
    except (ValueError, TypeError):
        return 'DB_URL', 'DATABASE_URL cannot be parsed; percent-encode reserved characters in the password.'
    return None


def safe_db_diagnose(exc, url):
    issue = validate_url_shape(url)
    if issue is not None:
        return issue
    return classify_database_error(exc)
