"""One-time opt-in import of V5 paper_accounts.sqlite3 into user-owned PG tables."""
import argparse, getpass, os, sqlite3
from cloud_db import connect,init_db
p=argparse.ArgumentParser()
p.add_argument('--sqlite',required=True,help='Path to original paper_accounts.sqlite3 file')
p.add_argument('--username',required=True,help='Existing cloud login username')
a=p.parse_args()
url=os.getenv('DATABASE_URL') or getpass.getpass('Cloud PostgreSQL DATABASE_URL (hidden): ')
if not os.path.isfile(a.sqlite):raise SystemExit('Local SQLite file not found')
init_db(url)
s=sqlite3.connect(a.sqlite);s.row_factory=sqlite3.Row
with connect(url) as db:
    user=db.execute('SELECT id FROM users WHERE username=%s',(a.username.lower(),)).fetchone()
    if not user:raise SystemExit('Cloud user not found. Provision account first.')
    uid=user['id']
    already=sum(db.execute(f'SELECT COUNT(*) AS n FROM {t} WHERE user_id=%s',(uid,)).fetchone()['n'] for t in ('accounts','orders','valuations'))
    if already:raise SystemExit('Cloud user already has paper-account records. Import only into an empty cloud account to avoid duplicates.')
    for tbl,cols in [
        ('accounts',['market','mode','cash','initial_cash','qty','avg_price','realized','day_idx']),
        ('orders',['market','mode','created_at','side','lots','order_type','limit_price','status','submitted_price','executed_at','executed_price','reason']),
        ('valuations',['market','mode','observation_date','price','cash','qty','equity','margin','recorded_at'])]:
        try: rows=s.execute('SELECT '+','.join(cols)+' FROM '+tbl).fetchall()
        except sqlite3.Error as exc:raise SystemExit(f'Missing SQLite table {tbl}: {exc}')
        placeholders=','.join(['%s']*(len(cols)+1))
        names=','.join(['user_id']+cols)
        for row in rows:
            values=[uid]+[row[c] for c in cols]
            db.execute(f'INSERT INTO {tbl}({names}) VALUES({placeholders})',values)
        print(tbl,'rows imported:',len(rows))
    db.commit()
s.close()
print('Local SQLite file unchanged. Check paper accounts in cloud application.')
