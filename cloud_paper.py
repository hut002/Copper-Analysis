"""Cloud PostgreSQL paper trading adapter. Every read and write is scoped to auth user id."""
from __future__ import annotations
from datetime import datetime,timezone
import pandas as pd
from cloud_db import connect
SPECS={'SHFE':{'multiplier':5,'currency':'CNY','tick':10.0},'LME_3M':{'multiplier':25,'currency':'USD','tick':0.5}}

class UserConn:
    def __init__(self,user_id):
        self.c=connect()
        self.user_id=int(user_id)
    def close(self): self.c.close()
    def commit(self): self.c.commit()
    def execute(self,sql,params=()): return self.c.execute(sql,params)

def connection(user_id):return UserConn(user_id)
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def reset(c,market,capital,mode='replay',day_idx=0):
    if capital<=0 or mode not in ('replay','forward'):raise ValueError('Invalid capital or mode')
    c.execute('DELETE FROM orders WHERE user_id=%s AND market=%s AND mode=%s',(c.user_id,market,mode))
    c.execute('DELETE FROM valuations WHERE user_id=%s AND market=%s AND mode=%s',(c.user_id,market,mode))
    c.execute('''INSERT INTO accounts(user_id,market,mode,cash,initial_cash,qty,avg_price,realized,day_idx)
        VALUES(%s,%s,%s,%s,%s,0,0,0,%s) ON CONFLICT(user_id,market,mode)
        DO UPDATE SET cash=excluded.cash,initial_cash=excluded.initial_cash,qty=0,
        avg_price=0,realized=0,day_idx=excluded.day_idx''',(c.user_id,market,mode,capital,capital,day_idx));c.commit()
def account(c,market,mode):
    return c.execute('SELECT * FROM accounts WHERE user_id=%s AND market=%s AND mode=%s',(c.user_id,market,mode)).fetchone()
def place(c,market,mode,side,lots,order_type,limit_price,reference_price):
    if not account(c,market,mode): raise ValueError('Create account first')
    if side not in ('BUY','SELL') or order_type not in ('MARKET','LIMIT'): raise ValueError('Invalid order parameters')
    if lots<=0 or lots>100000 or int(lots)!=lots: raise ValueError('Invalid number of lots')
    if order_type=='LIMIT' and (limit_price is None or limit_price<=0):raise ValueError('Limit price required')
    c.execute('''INSERT INTO orders(user_id,market,mode,created_at,side,lots,order_type,limit_price,status,submitted_price)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(c.user_id,market,mode,now(),side,int(lots),order_type,limit_price,'PENDING',reference_price));c.commit()
def equity(a,price,market,margin_rate):
    mult=SPECS[market]['multiplier'];unreal=a['qty']*(price-a['avg_price'])*mult
    margin=abs(a['qty'])*price*mult*margin_rate
    return {'unrealized':unreal,'margin':margin,'equity':a['cash']+unreal,'free_margin':a['cash']+unreal-margin}
def execute(c,market,mode,price,observation_date,margin_rate=.12,fee_per_lot=10.,ohlc=None):
    if price<=0: raise ValueError('Positive observed price required')
    a=c.execute('SELECT * FROM accounts WHERE user_id=%s AND market=%s AND mode=%s FOR UPDATE',(c.user_id,market,mode)).fetchone()
    if not a:raise ValueError('Account not found')
    orders=c.execute('SELECT * FROM orders WHERE user_id=%s AND market=%s AND mode=%s AND status=%s ORDER BY id FOR UPDATE',(c.user_id,market,mode,'PENDING')).fetchall()
    filled=rejected=0;mult=SPECS[market]['multiplier'];a=dict(a)
    for o in orders:
        if mode=='replay':
            bar=ohlc or {};op=float(bar.get('open',price));hi=float(bar.get('high',max(op,price)));lo=float(bar.get('low',min(op,price)))
            if o['order_type']=='MARKET': fill=op
            elif o['side']=='BUY':
                if lo>o['limit_price']: continue
                fill=min(op,o['limit_price'])
            else:
                if hi<o['limit_price']:continue
                fill=max(op,o['limit_price'])
        else:
            if o['order_type']=='LIMIT' and ((o['side']=='BUY' and price>o['limit_price']) or (o['side']=='SELL' and price<o['limit_price'])):continue
            fill=price
        dq=o['lots']*(1 if o['side']=='BUY' else -1);qold=a['qty'];qnew=qold+dq;avg=a['avg_price'];realized=0
        if qold==0 or qold*dq>0: avgnew=(abs(qold)*avg+abs(dq)*fill)/abs(qnew)
        else:
            closed=min(abs(qold),abs(dq));realized=closed*(fill-avg)*mult*(1 if qold>0 else -1)
            avgnew=avg if qnew!=0 and qold*qnew>0 else (fill if qnew else 0)
        cash=a['cash']+realized-fee_per_lot*o['lots'];test=equity({'cash':cash,'qty':qnew,'avg_price':avgnew},fill,market,margin_rate)
        if test['free_margin']< -1e-8:
            c.execute('UPDATE orders SET status=%s,reason=%s WHERE id=%s AND user_id=%s',('REJECTED','Insufficient free margin',o['id'],c.user_id));rejected+=1;continue
        a.update(cash=cash,qty=qnew,avg_price=avgnew,realized=a['realized']+realized)
        c.execute('UPDATE orders SET status=%s,executed_at=%s,executed_price=%s WHERE id=%s AND user_id=%s',('FILLED',str(observation_date),fill,o['id'],c.user_id));filled+=1
    c.execute('''UPDATE accounts SET cash=%s,qty=%s,avg_price=%s,realized=%s WHERE user_id=%s AND market=%s AND mode=%s''',
       (a['cash'],a['qty'],a['avg_price'],a['realized'],c.user_id,market,mode))
    e=equity(a,price,market,margin_rate)
    c.execute('''INSERT INTO valuations(user_id,market,mode,observation_date,price,cash,qty,equity,margin,recorded_at)
       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(c.user_id,market,mode,str(observation_date),price,a['cash'],a['qty'],e['equity'],e['margin'],now()))
    c.commit();return {'filled':filled,'rejected':rejected,**e}
def set_index(c,market,mode,day_idx):
    c.execute('UPDATE accounts SET day_idx=%s WHERE user_id=%s AND market=%s AND mode=%s',(int(day_idx),c.user_id,market,mode));c.commit()
def rows(c,table,market,mode):
    if table not in ('orders','valuations'):raise ValueError('Invalid table')
    with c.c.cursor() as cur:
        cur.execute(f'SELECT * FROM {table} WHERE user_id=%s AND market=%s AND mode=%s ORDER BY id',(c.user_id,market,mode))
        result=cur.fetchall()
    return pd.DataFrame(result,columns=[x.name for x in cur.description]) if result else pd.DataFrame(columns=['id','status'] if table=='orders' else ['observation_date','equity'])
def cancel_order(c,market,mode,order_id):
    cur=c.execute("UPDATE orders SET status='CANCELLED',reason='User cancelled' WHERE id=%s AND user_id=%s AND market=%s AND mode=%s AND status='PENDING'",(int(order_id),c.user_id,market,mode))
    c.commit();return cur.rowcount==1
