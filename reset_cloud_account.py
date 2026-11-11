"""Private reset/create admin tool for Copper Quant Cloud V6.1.
Does not log/store database credentials or passwords.
Run locally, never upload this utility with credentials to GitHub.
"""
import getpass
import hashlib
import hmac
import secrets
import sys
from datetime import datetime

HOST = 'aws-0-ap-northeast-1.pooler.supabase.com'
PORT = 5432
DATABASE = 'postgres'
USER = 'postgres.ofljdadmotifjhenfcvj'
ITERATIONS = 600_000


def read_secret(label):
    try:
        return getpass.getpass(label)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit('\nCancelled')


def main():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise SystemExit('Missing psycopg. Run: python -m pip install "psycopg[binary]"')
    print('Copper Quant Cloud V6.1 - Reset Existing Account / Create First Account')
    print('Database: Supabase Session Pooler (settings embedded; password not stored)')
    username = input('Account username [shyx]: ').strip().lower() or 'shyx'
    if not (3 <= len(username) <= 64 and username.replace('_', '').replace('-', '').isalnum()):
        raise SystemExit('Invalid username (3-64 letters, digits, - or _)')
    db_password = read_secret('Supabase DATABASE password (hidden): ')
    if not db_password:
        raise SystemExit('Database password cannot be blank.')
    new_password = read_secret('NEW Copper Quant login password (14+ chars, hidden): ')
    confirmation = read_secret('Repeat NEW Copper Quant login password: ')
    if len(new_password) < 14:
        raise SystemExit('New login password must have at least 14 characters.')
    if not hmac.compare_digest(new_password, confirmation):
        raise SystemExit('Passwords do not match. No changes made.')
    salt = secrets.token_hex(32)
    digest = hashlib.pbkdf2_hmac('sha256', new_password.encode('utf-8'), bytes.fromhex(salt), ITERATIONS).hex()
    del new_password, confirmation
    try:
        with psycopg.connect(
            host=HOST, port=PORT, dbname=DATABASE, user=USER, password=db_password,
            sslmode='require', connect_timeout=15, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM users WHERE username=%s FOR UPDATE', (username,))
                existing = cur.fetchone()
                if existing:
                    cur.execute('UPDATE users SET password_salt=%s,password_hash=%s WHERE id=%s',
                                (salt, digest, existing['id']))
                    action = 'RESET existing account password (account ID preserved)'
                else:
                    cur.execute('INSERT INTO users(username,password_salt,password_hash) VALUES(%s,%s,%s)',
                                (username,salt,digest))
                    action = 'CREATED new account'
                cur.execute('DELETE FROM login_attempts WHERE username=%s', (username,))
            conn.commit()
        print('\nSUCCESS:', action)
        print('Username:', username)
        print('Account unlocked; use your NEW password at the Streamlit login page.')
        print('Trade data and existing user ID are preserved when resetting.')
    except psycopg.OperationalError as exc:
        m = str(exc).lower()
        label = 'DB_CONNECTION'
        if 'password authentication failed' in m: label = 'DB_AUTH (Supabase database password incorrect)'
        elif 'tenant or user not found' in m: label = 'DB_POOLER_USER'
        elif 'translate host name' in m or 'name resolution' in m: label = 'DB_DNS'
        elif 'timeout' in m or 'timed out' in m: label = 'DB_TIMEOUT'
        elif 'ssl' in m or 'certificate' in m: label = 'DB_TLS'
        print('Failed:', label, '\nNo account changes made.')
        raise SystemExit(1)
    except psycopg.Error as exc:
        print('Database error:', type(exc).__name__, '(no credentials shown)')
        print('Check database tables have been initialized. No account changes committed.')
        raise SystemExit(1)

if __name__ == '__main__':
    main()
