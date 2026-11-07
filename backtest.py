"""No-lookahead SMA cross paper strategy. Trades execute next bar open, no fabricated history."""
import numpy as np
import pandas as pd
from paper_engine import SPECS

def ma_crossover(df,market,short=20,long=60,initial=1000000.,fee=10.,margin_rate=.12,slippage_ticks=1,side_mode='both'):
    if short>=long or short<2:raise ValueError('Short MA must be below long MA')
    if not {'open','close'}.issubset(df):raise ValueError('Historical backtest requires OPEN and CLOSE columns; upload OHLC CSV')
    d=df.copy().sort_values('date').reset_index(drop=True)
    if d['open'].isna().any() or len(d)<long+3:raise ValueError('Insufficient valid daily open and close prices')
    d['short']=d.close.rolling(short).mean();d['long']=d.close.rolling(long).mean()
    mult=SPECS[market]['multiplier'];tick=SPECS[market]['tick'];qty=0;cash=float(initial);avg=0.;transactions=[];curve=[]
    for i in range(long+1,len(d)):
        prev=d.iloc[i-1];p_prev=d.iloc[i-2];bar=d.iloc[i];desired=qty
        cross_up=p_prev['short']<=p_prev['long'] and prev['short']>prev['long']
        cross_down=p_prev['short']>=p_prev['long'] and prev['short']<prev['long']
        if cross_up:desired=1
        if cross_down:desired=-1 if side_mode=='both' else 0
        if desired!=qty:
            delta=desired-qty;fill=float(bar.open)+np.sign(delta)*slippage_ticks*tick
            # check rough margin for new position; capacity/cash can vary with prices
            realized=0
            if qty and (np.sign(delta)!=np.sign(qty)):
                realized=qty*(fill-avg)*mult
            cost=abs(delta)*fee
            candidate_cash=cash+realized-cost
            newavg=fill if desired else 0
            margin=abs(desired)*fill*mult*margin_rate
            if candidate_cash + desired*(float(bar.close)-newavg)*mult>=margin:
                cash=candidate_cash;qty=desired;avg=newavg
                transactions.append({'date':str(pd.Timestamp(bar.date).date()),'side':'BUY' if delta>0 else 'SELL','contracts':abs(delta),'fill':fill,'commission':cost,'realized':realized})
        mark=float(bar.close);net=cash+qty*(mark-avg)*mult
        curve.append({'date':str(pd.Timestamp(bar.date).date()),'equity':net,'close':mark,'position':qty})
    result=pd.DataFrame(curve);fills=pd.DataFrame(transactions)
    if result.empty:raise ValueError('No backtest observations')
    result['drawdown']=result.equity/result.equity.cummax()-1
    dr=result.equity.pct_change().dropna()
    stats={'ending_equity':float(result.equity.iloc[-1]),'total_return':float(result.equity.iloc[-1]/initial-1), 'max_drawdown':float(result.drawdown.min()),'executions':len(fills),'daily_sharpe':float(dr.mean()/dr.std()*np.sqrt(252)) if len(dr)>2 and dr.std()>0 else float('nan')}
    return result,fills,stats
