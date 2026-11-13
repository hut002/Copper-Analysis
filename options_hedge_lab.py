"""Options inventory hedging lab: historical spot paths with theoretical option premiums.
This is NOT a backtest using historical executed option trades.
"""
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

STRATEGIES=['No hedge','Long put','Collar','Put spread','Short futures']

def cdf(x): return (1+math.erf(x/math.sqrt(2)))/2

def black76(f,k,days,iv,rate,kind):
    t=days/252
    if t<=0: return max(0,f-k) if kind=='call' else max(0,k-f)
    v=max(iv,.0001)*math.sqrt(t); d1=(math.log(f/k)+v*v/2)/v;d2=d1-v
    disc=math.exp(-rate*t)
    return disc*(f*cdf(d1)-k*cdf(d2)) if kind=='call' else disc*(k*cdf(-d2)-f*cdf(-d1))

def price_path_pnl(s0,s1,qty,iv,days=63,rate=.02,put_pct=.99,call_pct=1.06,low_pct=.90,fee=20):
    kp=s0*put_pct;kc=s0*call_pct;kl=s0*low_pct
    pp=black76(s0,kp,days,iv,rate,'put');cp=black76(s0,kc,days,iv,rate,'call');lp=black76(s0,kl,days,iv,rate,'put')
    physical=s1-s0
    per={'No hedge':physical,
         'Long put':physical+max(kp-s1,0)-pp-fee,
         'Collar':physical+max(kp-s1,0)-max(s1-kc,0)-pp+cp-2*fee,
         'Put spread':physical+max(kp-s1,0)-max(kl-s1,0)-pp+lp-2*fee,
         'Short futures':-fee}
    return {k:v*qty for k,v in per.items()}

def clean(df):
    x=df[['date','close']].copy();x.date=pd.to_datetime(x.date,errors='coerce');x.close=pd.to_numeric(x.close,errors='coerce')
    return x.dropna().query('close > 0').sort_values('date').drop_duplicates('date').reset_index(drop=True)

def historical(df,notional,period=63,prior=60,iv_multiplier=1.2,iv_min=.15,base_margin=.03,**kwargs):
    d=clean(df)
    if len(d)<prior+4*period+1: raise ValueError('Need at least 313+ trading-day observations: 60-day prior volatility window plus four 63-trading-day quarters. Please load at least ~16 months.')
    last=len(d)-1
    output=[]
    for q in range(4):
        i=last-4*period+q*period;j=i+period
        r=np.log(d.close.iloc[i-prior:i+1]).diff().dropna();iv=max(iv_min,float(r.std()*np.sqrt(252))*iv_multiplier)
        s0=float(d.close.iloc[i]);s1=float(d.close.iloc[j]);qty=notional/s0
        for strategy,pnl in price_path_pnl(s0,s1,qty,iv,days=period,**kwargs).items():
            pnl += notional*base_margin  # explicitly assumed trade gross margin, NOT observed sales invoices
            output.append(dict(Quarter=q+1,Start=str(d.date.iloc[i].date()),End=str(d.date.iloc[j].date()),Strategy=strategy,
                               Entry=s0,Exit=s1,IV_assumed=iv,Notional=notional,Quantity_t=qty,**{'P&L':pnl,'P&L_%':100*pnl/notional}))
    return pd.DataFrame(output)

def future_scenarios(df,notional,strategy,period=63,paths=4000,iv_multiplier=1.2,iv_min=.15,base_margin=.03,seed=402,**kwargs):
    d=clean(df);logs=np.log(d.close).diff().dropna().values[-252:]
    if len(logs)<70:raise ValueError('Need at least 70 observations for forward scenarios')
    s0=float(d.close.iloc[-1]);qty=notional/s0
    iv=max(iv_min,float(np.std(logs[-60:],ddof=1)*np.sqrt(252))*iv_multiplier)
    rng=np.random.default_rng(seed);out=[]
    for _ in range(paths):
        seq=[]
        while len(seq)<period:
            i=int(rng.integers(0,len(logs)-4));seq.extend(logs[i:i+5])
        s1=s0*math.exp(sum(seq[:period]));pnl=price_path_pnl(s0,s1,qty,iv,days=period,**kwargs)[strategy]+notional*base_margin
        out.append({'Terminal copper price':s1,'Profit_or_loss':pnl})
    return pd.DataFrame(out),iv

def render(data,sources,zh):
    t=lambda cn,en:cn if zh else en
    st.subheader(t('铜期权现货套保：历史季度回测 + 未来市场情景','Copper inventory option hedges: quarterly backtest + forward simulation'))
    st.warning(t('真实历史铜价 + Black-76 理论期权权利金；并非交易所历史期权成交回测。未来价格为统计模拟，不能作为未来成交价。','Real historical copper closes + theoretical Black-76 option premiums. NOT a backtest of historical option fills. Forward market paths are simulations, not future actual quotes.'))
    if not data:
        st.info(t('请先在左侧加载至少16个月的铜价历史日线。','Load 16+ months of actual copper daily price observations from the sidebar.'))
        return
    market=st.selectbox(t('交易市场','Market'),list(data),key='op_market'); d=clean(data[market]); unit='CNY' if market=='SHFE' else 'USD'
    st.caption(f"{sources.get(market,'')} | {len(d)} records | {d.date.iloc[0].date()}–{d.date.iloc[-1].date()} | {unit}")
    a,b,c,d1=st.columns(4)
    val=a.number_input(t('现货库存价值（所选市场币种）','Inventory notional (market currency)'),min_value=10000.,value=10000000.,step=100000.,key='op_value')
    p=b.number_input(t('买入看跌期权K/初始价','Long put K / entry'),min_value=.75,max_value=1.1,value=.99,step=.01,key='op_put')
    call=c.number_input(t('领口卖出看涨K/初始价','Collar short call K / entry'),min_value=.9,max_value=1.4,value=1.06,step=.01,key='op_call')
    low=d1.number_input(t('价差下档看跌K/初始价','Put spread lower K / entry'),min_value=.5,max_value=.99,value=.90,step=.01,key='op_low')
    a,b,c=st.columns(3)
    mult=a.slider(t('隐含波动率/前60日实现波动率系数','IV multiplier over prior 60-day realized vol'),.7,2.,1.2,.1,key='op_ivmult')
    floor=b.slider(t('假设IV下限','Assumed IV floor'),.05,.4,.15,.01,key='op_floor')
    fee=c.number_input(t('每个期权腿每吨费用（假设）','Fee per option leg per tonne (assumed)'),min_value=0.,value=20.,step=5.,key='op_fee')
    margin=st.number_input(t('每周期假设贸易毛利率（非历史已实现）','Assumed trade margin per cycle (NOT actual realized)'),min_value=-.1,max_value=.5,value=.03,step=.005,key='op_margin')
    if not(low<p<call):st.error('Require lower put < long put < call strike');return
    kwargs=dict(put_pct=p,call_pct=call,low_pct=low,fee=fee)
    st.markdown('#### '+t('过去一年：四个不重叠的63交易日周期','Past year: four nonoverlapping 63-session cycles'))
    try:
        hist=historical(data[market],val,iv_multiplier=mult,iv_min=floor,base_margin=margin,**kwargs)
        st.dataframe(hist[['Quarter','Start','End','Strategy','IV_assumed','P&L','P&L_%']],hide_index=True,use_container_width=True)
        summary=hist.groupby('Strategy',as_index=False).agg(Total_PnL=('P&L','sum'),Average_quarter=('P&L','mean'),Worst_quarter=('P&L','min'))
        st.dataframe(summary,hide_index=True,use_container_width=True)
        st.bar_chart(hist.pivot(index='Quarter',columns='Strategy',values='P&L'))
        st.download_button(t('导出全部回测','Download full backtest CSV'),hist.to_csv(index=False).encode('utf-8-sig'),file_name=f'{market}_option_backtest.csv',key='op_hist_download')
    except Exception as exc: st.info(t('历史回测不可用：','Historical backtest unavailable: ')+str(exc))
    st.markdown('#### '+t('未来三个月：Bootstrap情景','Next three months: bootstrap scenarios'))
    strategy=st.selectbox(t('策略','Strategy'),STRATEGIES,index=1,key='op_strategy')
    try:
        sims,iv=future_scenarios(data[market],val,strategy,iv_multiplier=mult,iv_min=floor,base_margin=margin,**kwargs)
        q=sims.Profit_or_loss
        k=st.columns(4);k[0].metric(t('平均模拟盈亏','Simulated mean P&L'),f'{q.mean():,.0f}')
        k[1].metric(t('5%盈亏分位数','5th pct P&L'),f'{q.quantile(.05):,.0f}')
        k[2].metric(t('亏损路径占比','Loss path frequency'),f'{(q<0).mean():.1%}')
        k[3].metric(t('模型期权IV','Modeled option IV'),f'{iv:.1%}')
        fig=go.Figure(go.Histogram(x=q,nbinsx=50));fig.update_layout(title='Simulated 63-session portfolio P&L',xaxis_title=unit,height=340)
        st.plotly_chart(fig,use_container_width=True)
        st.download_button(t('导出情景路径','Download scenarios CSV'),sims.to_csv(index=False).encode('utf-8-sig'),file_name=f'{market}_future_scenarios.csv',key='op_future_download')
    except Exception as exc:st.error(f'{type(exc).__name__}: {exc}')
    st.caption(t('固定贸易毛利仅按用户输入假设，不含再生铜品质折价、汇率、基差、关税及期权美式提前行权；全部结果是以期货价代替现货结算基准的简化假设。股票上市公司请先获得套保授权。','Assumed trade margin is user supplied, NOT observed. Excludes recycled-copper grade discounts, FX, basis, customs costs, American early exercise and actual clearing margin. Futures close is used as a proxy for spot settlement. Governance authorization required.'))
