"""Regime-conditioned, inventory-backed copper risk simulation.

No live execution, no historical option-chain fills, no FX/basis model.
Futures option premiums use a European Black-76 proxy with ex-ante 60D realized
volatility * user multiplier. Contract sizes/lots and SHFE exercise mechanics are
NOT represented by theoretical continuous tonne quantities.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
def _cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def black76(f,k,days,iv,rate,kind):
    """European-style theoretical futures option, per tonne."""
    tau=max(0.,float(days))/252.
    if tau<=0 or iv<=0:
        return max(f-k,0.) if kind=='call' else max(k-f,0.)
    v=iv*math.sqrt(tau)
    d1=(math.log(f/k)+v*v/2)/v;d2=d1-v
    disc=math.exp(-rate*tau)
    return disc*(f*_cdf(d1)-k*_cdf(d2)) if kind=='call' else disc*(k*_cdf(-d2)-f*_cdf(-d1))

def clean(raw):
    d=raw[['date','close']].copy()
    d['date']=pd.to_datetime(d['date'],errors='coerce')
    d['close']=pd.to_numeric(d['close'],errors='coerce')
    return d.dropna().query('close > 0').sort_values('date').drop_duplicates('date').reset_index(drop=True)


NAMES = ('Unhedged', 'Protective put', 'Collar', 'Short futures', 'Put spread', 'Regime adaptive')

def regime_indicators(prices: pd.DataFrame) -> pd.DataFrame:
    """All signals use dates <= the signal date, never the evaluation horizon."""
    d = clean(prices)
    p = d['close']
    for window in (20, 60, 120):
        d[f'ma{window}'] = p.rolling(window, min_periods=window).mean()
    d['rv60'] = np.log(p).diff().rolling(60, min_periods=60).std() * np.sqrt(252)
    d['trend_strength'] = abs(d.ma20 / d.ma60 - 1)
    d['trend_pct'] = p.pct_change(60)
    bull = (d.ma20 > d.ma60) & (d.ma60 > d.ma120) & (d.trend_pct > .02)
    bear = (d.ma20 < d.ma60) & (d.ma60 < d.ma120) & (d.trend_pct < -.02)
    range_ = (d.trend_strength < .025) & (d.trend_pct.abs() < .07)
    d['regime'] = np.select([bull, bear, range_], ['Bull', 'Bear', 'Range'], default='Uncertain')
    d.loc[d.ma120.isna(), 'regime'] = 'Insufficient history'
    # Regime is a descriptive heuristic; not an ADX calculation.
    return d

def _put(s,k): return max(k-s, 0.0)
def _call(s,k): return max(s-k, 0.0)

def option_trade_pnl(spot0, spot1, tonnes, days, iv, rate, k_put,
                     k_call, k_low, fee, base_trade_margin):
    """All prices and fees are denominated PER TONNE in the selected market currency.

    Base margin is an explicit user assumption; it is NOT a realized trade invoice.
    Short futures P&L equals -(S1-S0)*tonnes and ignores variation-margin timing.
    """
    pp=black76(spot0,k_put,days,iv,rate,'put')
    cp=black76(spot0,k_call,days,iv,rate,'call')
    lp=black76(spot0,k_low,days,iv,rate,'put')
    delta=spot1-spot0
    base=delta + base_trade_margin*spot0
    result={
        'Unhedged': base,
        'Protective put': base+_put(spot1,k_put)-pp-fee,
        'Collar': base+_put(spot1,k_put)-_call(spot1,k_call)-pp+cp-2*fee,
        'Short futures': base-delta-fee,
        'Put spread': base+_put(spot1,k_put)-_put(spot1,k_low)-pp+lp-2*fee,
    }
    return {k:v*tonnes for k,v in result.items()}, {'put':pp,'call':cp,'low_put':lp}

def adaptive_weights(regime, allow_short_options=False):
    """Weights are fractions of physical copper benchmark exposure.

    Under strict controls short calls are NEVER used. At all times 100% of
    exposure has downside hedging by long puts and/or shorts against inventory.
    These are research model weights, not trading instructions.
    """
    if regime == 'Bear': return {'Protective put': .40, 'Short futures': .60}
    if regime == 'Range' and allow_short_options:
        return {'Protective put': .50, 'Collar': .50}
    return {'Protective put': 1.0}

def pnl_for_strategy(results, regime, name, allow_short_options=False):
    if name != 'Regime adaptive': return results[name], {name: 1.0}
    weights=adaptive_weights(regime, allow_short_options)
    return sum(results[k]*weight for k,weight in weights.items()), weights

def historical_regime_backtest(prices, notional=10_000_000, horizon=63, n_cycles=4,
                               prior_iv=60, iv_mult=1.2, iv_floor=.15, rate=.02,
                               put_pct=1.0, call_pct=1.06, low_pct=.90,
                               fee=20., base_margin=.03, allow_short_options=False):
    d=regime_indicators(prices)
    minimum=max(120,prior_iv)+n_cycles*horizon+1
    if len(d)<minimum:
        raise ValueError(f'Need at least {minimum} historical daily closes, including a 120-day signal warmup. Got {len(d)}.')
    rows=[]; last=len(d)-1
    for cycle in range(n_cycles):
        start=last-n_cycles*horizon+cycle*horizon
        end=start+horizon
        s0=float(d.close.iloc[start]); s1=float(d.close.iloc[end])
        rv=d.rv60.iloc[start]
        if not np.isfinite(rv):raise ValueError('Missing pre-entry volatility')
        iv=max(float(iv_floor),float(rv)*iv_mult)
        regime=d.regime.iloc[start]
        tonnes=notional/s0
        result, premiums=option_trade_pnl(s0,s1,tonnes,horizon,iv,rate,
                s0*put_pct,s0*call_pct,s0*low_pct,fee,base_margin)
        for strategy in NAMES:
            pnl,weights=pnl_for_strategy(result,regime,strategy,allow_short_options)
            rows.append(dict(Cycle=cycle+1,Start=str(d.date.iloc[start].date()),
                        End=str(d.date.iloc[end].date()),Regime_at_entry=regime,
                        Strategy=strategy,Entry=s0,Exit=s1,IV_model=iv,
                        Tonnes_theoretical=tonnes,Notional=notional,
                        PnL=pnl,Return_pct=100*pnl/notional,
                        Hedge_mix=' + '.join(f'{int(round(w*100))}% {k}' for k,w in weights.items()),
                        Put_premium_per_tonne=premiums['put']))
    return pd.DataFrame(rows)

def summary_frame(results, profit_target=0):
    records=[]
    for name,g in results.groupby('Strategy',sort=False):
        p=g.PnL.to_numpy(dtype=float)
        cutoff=np.quantile(p,.05)
        records.append({'Strategy':name,'Mean_three_month_PnL':p.mean(),
                        'Worst_three_month_PnL':p.min(),
                        'Total_four_cycles_PnL':p.sum(),
                        'Loss_cycles':int(np.sum(p<0)),
                        'Below_target_cycles':int(np.sum(p<profit_target)),
                        '5pct_CVaR_four_cycles_UNRELIABLE':float(np.mean(p[p<=cutoff]))})
    return pd.DataFrame(records).sort_values('Worst_three_month_PnL',ascending=False)

def forward_bootstrap(prices, notional=10_000_000,horizon=63, paths=2500,
                      iv_mult=1.2,iv_floor=.15,rate=.02,
                      put_pct=1.,call_pct=1.06,low_pct=.90,fee=20.,base_margin=.03,
                      allow_short_options=False,seed=42):
    d=regime_indicators(prices)
    if len(d)<121:raise ValueError('At least 121 historical observations required')
    regime=d.regime.iloc[-1]
    iv=max(float(iv_floor),float(d.rv60.iloc[-1])*iv_mult)
    s0=float(d.close.iloc[-1]);tonnes=notional/s0
    rets=np.log(d.close).diff().dropna().to_numpy()[-252:]
    if len(rets)<65:raise ValueError('Not enough historical daily returns')
    rng=np.random.default_rng(seed)
    block=5
    output=[]
    for path in range(paths):
        vals=[]
        while len(vals)<horizon:
            ix=int(rng.integers(0,len(rets)-block+1)); vals.extend(rets[ix:ix+block])
        s1=s0*math.exp(float(sum(vals[:horizon])))
        result,_=option_trade_pnl(s0,s1,tonnes,horizon,iv,rate,
                              s0*put_pct,s0*call_pct,s0*low_pct,fee,base_margin)
        for strategy in NAMES:
            pnl,weights=pnl_for_strategy(result,regime,strategy,allow_short_options)
            output.append({'Path':path,'Strategy':strategy,'Entry_regime':regime,
                           'Terminal_price':s1,'PnL':pnl,'Return_pct':100*pnl/notional})
    sims=pd.DataFrame(output)
    stats=[]
    for name,g in sims.groupby('Strategy',sort=False):
        x=g.PnL.to_numpy();cutoff=np.quantile(x,.05)
        stats.append({'Strategy':name,'Mean_PnL':x.mean(),'Median_PnL':np.median(x),
                      'P5_PnL':np.quantile(x,.05),'CVaR5_PnL':x[x<=cutoff].mean(),
                      'Loss_probability':(x<0).mean()})
    return sims,pd.DataFrame(stats).sort_values('CVaR5_PnL',ascending=False),iv,regime
