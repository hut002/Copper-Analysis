"""Regression tests for V6.1.2 journal rendering; no database credentials required."""
import re
import pandas as pd
from cloud_paper import rows

class FakeCursor:
    def __init__(self, db): self.db=db; self.description=None
    def __enter__(self): return self
    def __exit__(self,*args): self.description=None
    def execute(self, sql, params):
        assert re.search('WHERE user_id=%s AND market=%s AND mode=%s',sql)
        assert params==(42,'LME_3M','forward')
        table=re.search('FROM (\w+) WHERE',sql).group(1)
        self.data=self.db.rows[table]
        self.description=[object()]
    def fetchall(self): return self.data

class FakeDB:
    def __init__(self, dataset): self.rows=dataset
    def cursor(self): return FakeCursor(self)

class Conn:
    user_id=42
    def __init__(self, dataset): self.c=FakeDB(dataset)

order={'id':15,'user_id':42,'market':'LME_3M','mode':'forward','status':'PENDING','side':'SELL','lots':2}
val={'id':7,'user_id':42,'market':'LME_3M','mode':'forward','observation_date':'2026-11-11','equity':100000.0}
c=Conn({'orders':[order], 'valuations':[val]})
a=rows(c,'orders','LME_3M','forward')
b=rows(c,'valuations','LME_3M','forward')
assert a.loc[0,'status']=='PENDING' and a.loc[0,'id']==15
assert b.loc[0,'equity']==100000.0
c0=Conn({'orders':[], 'valuations':[]})
a0=rows(c0,'orders','LME_3M','forward')
b0=rows(c0,'valuations','LME_3M','forward')
assert a0.empty and 'status' in a0.columns and 'id' in a0.columns
assert b0.empty and 'equity' in b0.columns
try: rows(c,'users','LME_3M','forward')
except ValueError: pass
else: raise AssertionError('table whitelist not enforced')
print('PASS: populated orders, valuations, empty journals, closed cursor, table whitelist')
