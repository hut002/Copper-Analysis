"""Streamlit UI for the no-lookahead copper inventory regime hedge lab."""
import pandas as pd
import streamlit as st
from dynamic_hedge_engine import (regime_indicators,historical_regime_backtest,
                                 summary_frame,forward_bootstrap)

def render(data,sources,zh=True):
    T=lambda cn,en:cn if zh else en
    st.subheader(T('动态铜套保引擎：牛熊震荡识别 + 三个月回测','Dynamic Copper Hedging: market regimes + 3-month backtests'))
    st.warning(T('研究和模拟专用。使用已加载的真实历史铜价；期权权利金由 Black-76 理论模型估计，不代表期权历史成交。未来情景不是市场预测或交易指令。',
        'Research and simulation ONLY. Actual loaded copper history + theoretical Black-76 premiums, NOT historical option fills. Forward scenarios are not forecasts or trading instructions.'))
    if not data:
        st.info(T('请先在左侧加载真实历史价格（建议至少2年）；此模型至少需要约373个收盘价观测。',
                  'Load real history from the sidebar (2+ years recommended); this module needs ~373 closing observations.'))
        return
    market=st.selectbox(T('市场','Market'),list(data),key='dynamic_market')
    unit='CNY' if market=='SHFE' else 'USD'
    st.caption(f'{sources.get(market,"Unspecified data source")} | {unit} | '+T('伦铜美元库存不可直接当作人民币库存：须单独进行币种换算。','LME USD inventory must not be treated as RMB inventory without FX conversion.'))
    c=st.columns(4)
    notional=c[0].number_input(T('库存名义价值（按市场币种）','Inventory notional (market currency)'),min_value=10000.,value=10000000.,step=100000.,key='dyn_notional')
    margin=c[1].number_input(T('每次交易假设固定毛利率','Assumed base merchant margin per cycle'),min_value=-.1,max_value=.5,value=.03,step=.005,key='dyn_margin')
    iv_mult=c[2].slider(T('隐含/历史波动率系数','IV / prior realized vol'),.7,2.,1.2,.1,key='dyn_iv')
    iv_floor=c[3].slider(T('最低理论IV','Theoretical IV floor'),.05,.45,.15,.01,key='dyn_floor')
    c=st.columns(4)
    put=c[0].number_input(T('保护Put行权价/初始价','Put strike / entry'),min_value=.70,max_value=1.1,value=1.,step=.01,key='dyn_put')
    call=c[1].number_input(T('Collar看涨行权价/初始价','Collar call / entry'),min_value=.90,max_value=1.4,value=1.06,step=.01,key='dyn_call')
    low=c[2].number_input(T('Put spread低行权价/初始价','Put spread lower strike / entry'),min_value=.5,max_value=.99,value=.90,step=.01,key='dyn_low')
    fee=c[3].number_input(T('每腿每吨费用假设','Fee per tonne per leg'),min_value=0.,value=20.,step=5.,key='dyn_fee')
    short_ok=st.checkbox(T('研究模式：允许Collar卖出有现货覆盖的Call（默认禁止）',
                            'Research only: allow inventory-covered short call in collar (disabled by default)'),value=False,key='dyn_cover_call')
    st.caption(T('默认合规审慎模式：动态方案在牛市/震荡/不确定状态持有保护性Put；熊市采用60%空期货+40%Put。牛熊识别只使用当日及以前价格，在每次63交易日周期起点确定，不用未来信息切换策略。',
                 'Conservative default: long put in bull/range/uncertain, 60% short futures + 40% put in bear. Signals are computed using only observations available at cycle entry, not future information.'))
    if not (low<put<call):
        st.error(T('须满足低Put行权价 < 主Put行权价 < Call行权价','Require lower put strike < main put strike < call strike'))
        return
    params=dict(notional=notional,iv_mult=iv_mult,iv_floor=iv_floor,put_pct=put,
                call_pct=call,low_pct=low,fee=fee,base_margin=margin,allow_short_options=short_ok)
    d=regime_indicators(data[market])
    last=d.iloc[-1]
    states={'Bull':'牛市','Bear':'熊市','Range':'震荡','Uncertain':'不确定','Insufficient history':'数据不足'}
    st.metric(T('最新历史行情识别状态','Regime at last loaded date'),states.get(last.regime,last.regime) if zh else last.regime)
    st.caption(f"{str(last.date.date())} · MA20={last.ma20:,.2f} · MA60={last.ma60:,.2f} · MA120={last.ma120:,.2f} · RV60={last.rv60:.1%}")
    st.markdown('#### '+T('过去一年：四个不重叠的63交易日周期','Historical: four nonoverlapping 63-session cycles'))
    try:
        hist=historical_regime_backtest(data[market],**params)
        st.dataframe(hist[['Cycle','Start','End','Regime_at_entry','Strategy','Hedge_mix','PnL','Return_pct']],use_container_width=True,hide_index=True)
        st.bar_chart(hist.pivot(index='Cycle',columns='Strategy',values='PnL'))
        s=summary_frame(hist,notional*margin)
        st.dataframe(s.drop(columns=['5pct_CVaR_four_cycles_UNRELIABLE']),use_container_width=True,hide_index=True)
        st.caption(T('只有四个完整周期，不能据此可靠估计5% CVaR或判断策略长期优越性。',
                     'Four historical cycles are far too few to estimate a stable 5% CVaR or prove strategy superiority.'))
        st.download_button(T('下载详细回测CSV','Download historical CSV'),hist.to_csv(index=False).encode('utf-8-sig'),file_name=f'{market}_dynamic_hedge_historical.csv',key='dyn_hist_csv')
    except Exception as exc:
        st.info(T('历史回测未能运行：','Historical backtest unavailable: ')+str(exc))
    st.markdown('#### '+T('未来63交易日：Monte Carlo / Block Bootstrap情景','Forward 63-session block-bootstrap scenarios'))
    count=st.select_slider(T('模拟路径数量','Simulated paths'),options=[1000,2000,4000],value=2000,key='dyn_paths')
    try:
        sim,stats,iv,regime=forward_bootstrap(data[market],paths=count,**params)
        st.dataframe(stats,use_container_width=True,hide_index=True)
        focus=st.selectbox(T('风险分布策略','Risk distribution strategy'),list(stats.Strategy),key='dyn_focus')
        subset=sim[sim.Strategy==focus]
        import plotly.graph_objects as go
        fig=go.Figure(go.Histogram(x=subset.PnL,nbinsx=50))
        fig.update_layout(height=330,title=T('情景利润分布','Scenario P&L distribution'),xaxis_title=unit)
        st.plotly_chart(fig,use_container_width=True)
        st.caption(f'{T("情景起点状态","Starting regime")}: {regime} | '+T('用于理论权利金的IV','Theoretical premium IV')+f': {iv:.1%}')
        st.download_button(T('下载未来情景摘要','Download scenario summary'),stats.to_csv(index=False).encode('utf-8-sig'),file_name=f'{market}_dynamic_hedge_scenarios.csv',key='dyn_summ_csv')
    except Exception as exc:
        st.error(T('模拟失败：','Simulation failed: ')+str(exc))
    st.caption(T('模型不计再生铜回收率、现货基差、USD/CNY汇率、税费、融资和保证金逐日现金流。Black-76是欧式期权近似，不能覆盖上期所美式行权及期权流动性风险。动态规则不代表合规批准。',
                 'Excludes scrap grade/yield, physical-futures basis, FX, taxes, financing and futures variation-margin liquidity. Black-76 is a European proxy, not SHFE American exercise or market liquidity. Internal authorization is required.'))
