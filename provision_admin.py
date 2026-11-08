"""Run privately on your own machine; never put credentials into source or git."""
import argparse,getpass,os
from cloud_auth import create_user
from cloud_db import init_db
p=argparse.ArgumentParser();p.add_argument('--username',required=True);args=p.parse_args()
# Cloud settings can also be supplied via DB_HOST / DB_USER / DB_PASSWORD environment variables.
url=os.getenv('DATABASE_URL')
if not url and not (os.getenv('DB_HOST') and os.getenv('DB_USER') and os.getenv('DB_PASSWORD')):
    url=getpass.getpass('DATABASE_URL (input hidden, not saved): ')
if not url and not (os.getenv('DB_HOST') and os.getenv('DB_USER') and os.getenv('DB_PASSWORD')):
    raise SystemExit('Database URL or DB_HOST/DB_USER/DB_PASSWORD environment variables are required')
pwd=getpass.getpass('New password (14+ characters, hidden): ')
confirm=getpass.getpass('Confirm password: ')
if pwd!=confirm:raise SystemExit('Passwords do not match')
init_db(url)
create_user(args.username,pwd,url)
print('Account created securely. No password printed or stored in script.')
