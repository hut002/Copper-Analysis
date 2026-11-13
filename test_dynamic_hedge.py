import numpy as np
import pandas as pd
from dynamic_hedge_engine import (
  regime_indicators,historical_regime_backtest,forward_bootstrap,
  option_trade_pnl,adaptive_weights,summary_frame,
  period_return_report,period_return_summary)

def sample(kind='up',n=550):
    rng=np.random.default_rng(123)
    drift={'up':.001,'down':-.001,'range':0}[kind]
    returns=drift+rng.normal(0,.004,n)
    price=100000*np.exp(np.cumsum(returns))
    return pd.DataFrame({'date':pd.date_range('2024-01-01',periods=n,freq='B'),'close':price})

for kind in ('up','down','range'):
    d=sample(kind)
    state=regime_indicators(d)
    assert len(state)==550
    hist=historical_regime_backtest(d)
    assert len(hist)==24
    assert hist.groupby('Cycle').Strategy.nunique().eq(6).all()
    assert np.isfinite(hist.PnL).all()
    assert hist.Cycle.nunique()==4
    fs,stats,vol,reg=forward_bootstrap(d,paths=100,seed=42)
    assert len(fs)==600 and len(stats)==6
    assert fs.groupby('Path').Strategy.nunique().eq(6).all()
    assert np.isfinite(stats.CVaR5_PnL).all()
    assert summary_frame(hist).shape[0]==6

# Full-notional inventory hedge and short futures exactly offsets terminal benchmark move
for end in (75000,100000,125000):
    p,_=option_trade_pnl(100000,end,100,63,.2,.02,100000,106000,90000,20,.03)
    assert abs(p['Short futures']-(300000-2000))<1e-6
    assert abs(p['Unhedged']-((end-100000)*100+300000))<1e-6

assert adaptive_weights('Bear')=={'Protective put':.4,'Short futures':.6}
assert 'Collar' not in adaptive_weights('Range')
assert 'Collar' in adaptive_weights('Range',True)

# No lookahead: changing later prices cannot modify a historical entry signal
orig=sample('up')
changed=orig.copy();changed.loc[450:,'close']*=0.65
sa=regime_indicators(orig).regime.iloc[400]
sb=regime_indicators(changed).regime.iloc[400]
assert sa==sb

# Insufficient history gracefully fails
try:historical_regime_backtest(sample('up',200))
except ValueError:pass
else:raise AssertionError('Missing expected short-history error')
print('PASS dynamic hedging: 3 regimes, 4 quarters, 6 strategies, forecasts, hedge invariants, no-lookahead, short-data')

# Quarterly return accounting: each 3-month cycle uses FIXED inventory notional.
x=historical_regime_backtest(sample('up'))
r=period_return_report(x,10_000_000)
a=period_return_summary(x,10_000_000)
assert len(r)==24 and len(a)==6
assert (r.Period_months==3).all()
assert np.allclose(r.Quarter_return_pct,r.PnL/10_000_000*100)
assert np.allclose(r.Ending_equity_fixed,10_000_000+r.PnL)
for name,g in r.groupby('Strategy'):
    row=a[a.Strategy==name].iloc[0]
    assert np.isclose(row.Annual_PnL,g.PnL.sum())
    assert np.isclose(row.Annual_return_fixed_pct,g.Quarter_return_pct.sum())
print('PASS V6.4 quarterly P&L/return accounting, annual summary')
