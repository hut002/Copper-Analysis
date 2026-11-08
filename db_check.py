"""Safe CLI connectivity check. Accepts either env DB_* fields or a getpass DSN."""
import getpass, os
from cloud_db import connect,DatabaseConfigError,DatabaseConnectionError

def main():
    print('Copper Quant Cloud — private PostgreSQL check')
    print('Nothing secret is printed or written to disk.')
    url=None
    if not (os.getenv('DB_HOST') or os.getenv('DATABASE_URL')):
        url=getpass.getpass('Paste PostgreSQL URL (hidden, NOT saved): ').strip()
    try:
        with connect(url) as c:
            row=c.execute('SELECT current_database() AS name, 1 AS ok').fetchone()
            assert row['ok']==1
        print('DB_OK: connection and SELECT succeeded')
    except (DatabaseConfigError,DatabaseConnectionError) as exc:
        print(str(exc))
        raise SystemExit(1)
    except Exception as exc:
        print('DB_TEST_ERROR: '+type(exc).__name__)
        raise SystemExit(1)

if __name__=='__main__':main()
