"""Offline safety smoke checks; no actual cloud DB is contacted."""
import tempfile,sqlite3,ast,pathlib
from cloud_auth import password_hash
from cloud_paper import equity
from hedge_engine import scenario_table
import numpy as np
import pandas as pd

def run():
    root=pathlib.Path(__file__).parent
    for f in ['app.py','cloud_db.py','cloud_auth.py','cloud_paper.py','quant_engine.py','hedge_engine.py','backtest.py','provision_admin.py','migrate_local_sqlite.py']:
        ast.parse((root/f).read_text(encoding='utf-8'))
    assert password_hash('secret-pass','01'*32)==password_hash('secret-pass','01'*32)
    assert password_hash('secret-pass','02'*32)!=password_hash('secret-pass','01'*32)
    assert equity({'qty':2,'avg_price':100,'cash':10000},110,'SHFE',.12)['unrealized']==100
    tbl,info=scenario_table('SHFE',100,'inventory',100000,100000,1,np.array([95000.,100000.,105000.]),margin_rate=.12)
    assert info['lots']==20 and len(tbl)==3
    print('PASS: syntax + salted verifier + paper P&L + hedge scenarios')
if __name__=='__main__':run()
