"""Run privately on your own machine; never put credentials into source or git."""
import argparse,getpass,os
from cloud_auth import create_user
from cloud_db import init_db
p=argparse.ArgumentParser();p.add_argument('--username',required=True);args=p.parse_args()
url=os.getenv('DATABASE_URL') or getpass.getpass('DATABASE_URL (input hidden, not saved): ')
if not url:raise SystemExit('Database URL is required')
pwd=getpass.getpass('New password (14+ characters, hidden): ')
confirm=getpass.getpass('Confirm password: ')
if pwd!=confirm:raise SystemExit('Passwords do not match')
init_db(url)
create_user(args.username,pwd,url)
print('Account created securely. No password printed or stored in script.')
