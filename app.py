"""Bilingual local-only SHFE/LME copper quant + paper trading. Research / education, no broker connectivity."""
from datetime import date,timedelta
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from quant_engine import fetch_shfe,fetch_lme,normalize,metrics_and_indicators,monte_carlo
from hedge_engine import scenario_table,maturity_table
from cloud_paper import connection,account,reset,place,execute,equity,set_index,rows,SPECS,cancel_order
from backtest import ma_crossover

ROOT=Path(__file__).resolve().parent
from cloud_db import init_db,cache_save,cache_load
from cloud_auth import gate,change_credentials
st.set_page_config(page_title='Copper Quant + Paper Trading V5',page_icon='📈',layout='wide')
st.markdown('<style>.block-container{max-width:1650px;padding-top:1rem} [data-testid="stMetric"]{border:1px solid rgba(128,128,128,.18);padding:12px;border-radius:12px}</style>',unsafe_allow_html=True)
# Login before any market load or paper-account state is visible.
try:
    init_db()
except Exception as e:
    import logging
    logging.error("Database initialization failed: %s", type(e).__name__)
    st.error(
        f"Database initialization failed: {type(e).__name__}"
    )
    st.stop()
CURRENT_USER=gate()
with st.sidebar:
    st.caption(f"Signed in / 已登录: {CURRENT_USER['username']}")
    if st.button('Sign out / 退出登录',use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    with st.expander('Account settings / 账号管理'):
        with st.form('change_credentials'):
            new_name=st.text_input('New username / 新用户名',value=CURRENT_USER['username'])
            old=st.text_input('Current password / 原密码',type='password')
            new=st.text_input('New password (14+ chars) / 新密码',type='password')
            confirm=st.text_input('Confirm new password / 确认密码',type='password')
            change=st.form_submit_button('Change credentials / 修改凭据')
        if change:
            if new!=confirm:st.error('New passwords do not match / 两次密码不一致')
            else:
                try:
                    change_credentials(CURRENT_USER['id'],old,new_name,new)
                    st.success('Updated. Please sign in again / 修改成功，请重新登录')
                    for k in list(st.session_state):del st.session_state[k]
                    st.rerun()
                except Exception as ex:st.error(f'Account update failed / 修改失败: {type(ex).__name__}')


lang=st.sidebar.radio('Language / 语言',['中文','English'],horizontal=True,key='language')
ZH=(lang=='中文')
def tr(zh,en):return zh if ZH else en
NAMES={'SHFE':tr('沪铜主力连续','SHFE Copper Main Continuous'),'LME_3M':tr('伦铜3个月','LME Copper 3M')}
UNITS={'SHFE':'CNY/t','LME_3M':'USD/t'}
def fmt(n):return f'{n:,.2f}'
def pct(n):return f'{n:.2%}'
def chart(df,cols,title,height=380):
    fig=go.Figure()
    palette=['#38bdf8','#fbbf24','#34d399','#fb7185']
    for i,(key,label) in enumerate(cols):
        if key in df:fig.add_trace(go.Scatter(x=df.date,y=df[key],name=label,line=dict(width=2,color=palette[i%len(palette)])))
    fig.update_layout(template='plotly_dark',height=height,title=title,margin=dict(l=15,r=15,b=15,t=45),hovermode='x unified',legend=dict(orientation='h',y=1.06))
    return fig
@st.cache_data(ttl=3600,show_spinner=False)
def download(m,start,end):return fetch_shfe(start,end) if m=='SHFE' else fetch_lme(start,end)
def load_market(m,mode,file,start,end):
    if mode=='upload':
        if file is None:raise ValueError(tr('请上传CSV','Upload CSV first'))
        return normalize(pd.read_csv(file,encoding='utf-8-sig'),start,end,m), 'User CSV: '+file.name
    if mode=='cache':
        raw,source=cache_load(CURRENT_USER['id'],m)
        return normalize(raw,start,end,m),source
    return download(m,start,end)

def save_data(m,d,source):
    cache_save(CURRENT_USER['id'],m,d,source)

st.title(tr('铜期货量化分析与模拟交易终端','Copper Quantitative & Paper Trading Terminal'))
st.caption(tr('沪铜 SHFE + 伦铜 LME 3M | 云端部署 | 无实盘交易接口','SHFE Copper + LME Copper 3M | Cloud deployment | No live order-routing integration'))
with st.sidebar:
    st.subheader(tr('数据控制','Market data'))
    today=date.today();end=st.date_input(tr('截止日期','End date'),today);start=st.date_input(tr('开始日期','Start date'),today-timedelta(days=1100))
    selected_source=st.selectbox(tr('数据来源','Data source'),['download','cache','upload'],format_func=lambda x:{'download':tr('在线获取真实行情','Download public observations'),'cache':tr('云端数据库缓存','Cloud database cache'),'upload':tr('上传历史CSV','Upload CSV')}[x])
    uploads={}
    if selected_source=='upload':
        uploads['SHFE']=st.file_uploader('SHFE CSV',type=['csv'],key='shfef')
        uploads['LME_3M']=st.file_uploader('LME 3M CSV',type=['csv'],key='lmef')
    if st.button(tr('刷新/加载数据','Load / refresh observations'),type='primary',use_container_width=True):
        st.session_state['data']={};st.session_state['sources']={};st.session_state['errors']={}
        for m in ['SHFE','LME_3M']:
            try:
                d,src=load_market(m,selected_source,uploads.get(m),str(start),str(end))
                st.session_state['data'][m]=d;st.session_state['sources'][m]=src;save_data(m,d,src)
            except Exception as e:st.session_state['errors'][m]=f'{type(e).__name__}: {e}'
    st.caption(tr('数据必须来自真实历史报价。伦铜免费数据并非LME官方授权实时数据。','Only actual market observations are accepted. Free LME feeds are not licensed official real-time feeds.'))

for m,err in st.session_state.get('errors',{}).items():st.error(f'{NAMES[m]}: {err}')
data=st.session_state.get('data',{});sources=st.session_state.get('sources',{})
tab_names=[tr('市场概览','Overview'),tr('技术指标','Technicals'),tr('风险与蒙特卡洛','Risk & Monte Carlo'),tr('套保策略','Hedging'),tr('模拟交易','Paper trading'),tr('策略回测','Strategy backtest'),tr('外部模拟盘对账','External sim reconciliation')]
tabs=st.tabs(tab_names)
with tabs[0]:
    if not data:st.info(tr('请先从左侧获取真实行情，或上传CSV。模拟交易中的前向模式允许手动输入观察价。','Load real market history or CSV in the sidebar. Forward paper mode can use manually confirmed market quotes.'))
    else:
        rows_over=[]
        for m,d in data.items():
            rows_over.append({'Market/市场':NAMES[m],'Last date/日期':str(d.date.iloc[-1].date()),'Close/收盘价':float(d.close.iloc[-1]),'Unit/单位':UNITS[m],'Rows/行数':len(d),'Source/来源':sources.get(m,'')})
        st.dataframe(pd.DataFrame(rows_over),hide_index=True,use_container_width=True)
        for m,d in data.items():
            left,right=st.columns([3,1])
            with left:st.plotly_chart(chart(d,[('close','Close')],NAMES[m]),use_container_width=True)
            with right:
                st.metric(NAMES[m],fmt(d.close.iloc[-1]));st.caption(sources.get(m,''));st.download_button(tr('下载行情CSV','Download observations'),d.to_csv(index=False).encode('utf-8-sig'),file_name=f'{m}_history.csv',key=f'exp_{m}')
with tabs[1]:
    if data:
        m=st.selectbox(tr('市场','Market'),list(data),format_func=lambda k:NAMES[k],key='technical_market')
        d,s=metrics_and_indicators(data[m]);st.plotly_chart(chart(d,[('close','Close'),('MA20','MA20'),('MA60','MA60')],NAMES[m]),use_container_width=True)
        st.plotly_chart(chart(d,[('RSI14','RSI 14')],tr('相对强弱指数','Relative Strength Index')),use_container_width=True)
        st.plotly_chart(chart(d,[('MACD','MACD'),('MACD_signal','Signal')],'MACD'),use_container_width=True)
        c=st.columns(4)
        for i,(name,v) in enumerate([('MA20',s['MA20']),('MA60',s['MA60']),('RSI14',s['RSI14']),('MACD',s['MACD'])]):c[i].metric(name,fmt(v))
    else:st.info(tr('需要历史数据','Historical observations required'))
with tabs[2]:
    if data:
        m=st.selectbox(tr('市场','Market'),list(data),format_func=lambda k:NAMES[k],key='risk_market');d,s=metrics_and_indicators(data[m])
        c=st.columns(5)
        for i,(name,v) in enumerate([(tr('年化波动率','Annualized volatility'),s['annualized_volatility_3y']),(tr('1日VaR 95%','1-day VaR 95%'),s['historical_1d_95']['VaR']),(tr('1日CVaR 95%','1-day CVaR 95%'),s['historical_1d_95']['CVaR']),(tr('20日VaR 95%','20-day VaR 95%'),s['historical_20d_95']['VaR']),(tr('最大回撤','Max drawdown'),s['max_drawdown'])]):c[i].metric(name,pct(v))
        st.plotly_chart(chart(d,[('vol20','20D vol'),('vol60','60D vol')],tr('滚动年化波动率','Rolling annualized volatility')),use_container_width=True)
        paths=st.select_slider(tr('路径数量','Simulation paths'),[1000,2000,5000,10000,30000],value=5000)
        method=st.radio(tr('模拟方法','Simulation method'),['block_bootstrap','normal_log_returns'],horizontal=True)
        sim,curve=monte_carlo(d,paths=paths,horizon=20)
        fig=go.Figure();x=curve.day
        fig.add_trace(go.Scatter(x=list(x)+list(x[::-1]),y=list(curve[f'{method}_p95'])+list(curve[f'{method}_p05'][::-1]),fill='toself',fillcolor='rgba(56,189,248,.16)',line_color='rgba(0,0,0,0)',name='5%–95%'))
        for q,col in [('p05','#fb7185'),('p50','#38bdf8'),('p95','#34d399')]:fig.add_trace(go.Scatter(x=x,y=curve[f'{method}_{q}'],name=q,line_color=col))
        fig.update_layout(template='plotly_dark',title=tr('未来20交易日价格模拟（非未来行情）','20-trading-day Monte Carlo (NOT future market quotes)'),height=470,xaxis_title=tr('交易日','Trading days'),yaxis_title=UNITS[m])
        st.plotly_chart(fig,use_container_width=True)
        st.json(sim[method]);st.caption(tr('统计模拟不能用于前向模拟盘的成交价。','Simulated paths cannot be used as observed prices or fills in forward paper trading.'))
    else:st.info(tr('需要真实历史数据','Real historical observations required'))
with tabs[3]:
    st.subheader(tr('套期保值分析 / Hedge Strategy','Hedge Strategy Studio'))
    m=st.selectbox(tr('交易所','Market'),['SHFE','LME_3M'],format_func=lambda k:NAMES[k],key='hedgem')
    c1,c2,c3,c4=st.columns(4)
    physical=c1.selectbox(tr('现货敞口','Physical exposure'),['inventory','future_purchase'],format_func=lambda x:tr('已有库存：卖出套保','Inventory: short hedge') if x=='inventory' else tr('未来采购：买入套保','Future purchase: long hedge'))
    tons=c2.number_input(tr('现货吨数','Exposure tonnes'),min_value=0.0,value=100.,step=5.)
    ratio=c3.slider(tr('套保比例','Hedge ratio'),0,100,100)/100
    maturity=c4.date_input(tr('交付日期','Delivery date'),date.today()+timedelta(days=90),key='maturity')
    a,b,c,d=st.columns(4)
    spot=a.number_input(tr('现货参考价','Reference physical price'),min_value=.01,value=105000. if m=='SHFE' else 14000.,step=10.)
    future=b.number_input(tr('对应期限真实期货报价（手动）','Actual matched futures quote (manual)'),min_value=.01,value=106000. if m=='SHFE' else 14000.,step=10.)
    fx=c.number_input(tr('报表汇率系数','Report FX multiplier'),min_value=.0001,value=1.,step=.01)
    margin_rate=d.slider(tr('保证金率','Margin rate'),5,40,12)/100
    chosen_dates={1:st.number_input('1M quote',min_value=0.,value=0.,key='m1'),3:st.number_input('3M quote',min_value=0.,value=0.,key='m3'),6:st.number_input('6M quote',min_value=0.,value=0.,key='m6')}
    scenarios=spot*np.array([.85,.90,.95,1,1.05,1.10,1.15])
    tbl,info=scenario_table(m,tons,physical,spot,future,ratio,scenarios,fx=fx,margin_rate=margin_rate)
    c1,c2,c3=st.columns(3);c1.metric(tr('套保方向','Direction'),info['direction']);c2.metric(tr('对应手数','Lots'),str(info['lots']));c3.metric(tr('初始保证金（估计）','Estimated initial margin'),f"{info['initial_margin']:,.0f} {info['currency']}")
    st.dataframe(tbl,use_container_width=True,hide_index=True)
    st.line_chart(tbl.set_index('Scenario spot')[['Unhedged P&L','Hedged net P&L']]);st.dataframe(maturity_table(date.today(),maturity,chosen_dates,m,tons,ratio),hide_index=True,use_container_width=True)
    st.caption(tr('远期报价均为手动输入，非自动获取的可交易报盘。','Term quotes are user-provided, not executable automatic forward curves.'))
with tabs[4]:
    st.subheader(tr('虚拟资金账户与下单','Paper account and order entry'))
    st.warning(tr('仅用于教学与实验。不会将订单发送到证券软件或任何交易所。','Research and testing only. No order is transmitted to brokers or exchanges.'))
    mode=st.radio(tr('交易实验模式','Experiment mode'),['replay','forward'],format_func=lambda v:tr('历史逐日回放','Historical daily replay') if v=='replay' else tr('前向观察价模拟','Forward observed-quote paper trading'),horizontal=True)
    m=st.selectbox(tr('市场','Market'),['SHFE','LME_3M'],format_func=lambda k:NAMES[k],key='paper_market')
    st.caption(tr('沪铜主连/伦铜3M为参考序列。模拟成交假设不能替代具体合约的结算、换月与交割细则。','Continuous SHFE and rolling LME 3M are benchmarks: fills do not replicate prompt dates, rollover, clearing or delivery.'))
    conn=connection(CURRENT_USER['id']);a=account(conn,m,mode)
    start_cap=st.number_input(tr('初始模拟资金','Initial virtual capital'),min_value=1000.,value=1000000. if m=='SHFE' else 200000.,step=1000.,key=f'cap_{m}_{mode}')
    if st.button(tr('新建 / 重置该模拟账户','Create / reset this paper account'),key='reset_paper'):
        reset(conn,m,start_cap,mode,day_idx=0);st.rerun()
    if a is None:st.info(tr('先创建该市场/模式的虚拟账户。','Create a virtual account for this market and mode first.'))
    else:
        margin=st.slider(tr('模拟保证金比例','Paper margin %'),5,40,12,key=f'marg_{m}_{mode}')/100
        fee=st.number_input(tr('每手单边手续费','Fee per lot / side'),min_value=0.,value=10.,key=f'fee_{m}_{mode}')
        obs=None;obsdate=None;history=None
        if mode=='replay':
            history=data.get(m)
            if history is None:st.error(tr('历史回放需先从左侧加载行情。','Load historical observations in the sidebar for replay mode.'))
            elif len(history)<3:st.error(tr('历史数据不足','Insufficient rows'))
            else:
                idx=min(int(a['day_idx']),len(history)-2);shown=history.iloc[:idx+1].copy();bar=history.iloc[idx];obs=float(bar.close);obsdate=str(bar.date.date())
                st.metric(tr('当前回放日期 / 收盘价','Current replay date / close'),f'{obsdate} / {fmt(obs)} {UNITS[m]}')
                st.plotly_chart(chart(shown,[('close','Close')],tr('可见历史（不泄露未来K线）','Visible history (no lookahead)')),use_container_width=True)
                st.caption(tr('当前订单会在点击“下一交易日”时，按下一根K线开盘价成交；限价单需要触及该价位。','Orders submitted today execute on the NEXT bar open; limits fill only if next bar trades through the limit.'))
        else:
            st.info(tr('请从终端/行情商核实新报价后手动输入。当前模式不连接实时行情。','Confirm a new quote from your market terminal/vendor and enter it manually. No live feed is connected.'))
            obs=st.number_input(tr('本次观察价格','Observed quote'),min_value=.01,value=105000. if m=='SHFE' else 14000.,step=10.,key=f'forward_price_{m}')
            obsdate=st.text_input(tr('报价时间和来源','Quote timestamp + source'),value='',placeholder=tr('例：2026-11-05 14:30 CST, XX行情终端','e.g. 2026-11-05 14:30 CST, vendor name'))
        if obs is not None:
            e=equity(a,obs,m,margin)
            cc=st.columns(5)
            for i,(name,value) in enumerate([(tr('权益','Equity'),e['equity']),(tr('可用权益','Free margin'),e['free_margin']),(tr('浮动盈亏','Unrealized P&L'),e['unrealized']),(tr('已实现盈亏','Realized P&L'),a['realized']),(tr('净持仓(手)','Net position (lots)'),a['qty'])]):cc[i].metric(name,fmt(value))
            st.caption(f"{tr('账户币种','Currency')}: {SPECS[m]['currency']} | {tr('每手吨数','Tonnes per lot')}: {SPECS[m]['multiplier']}")
            if e['free_margin'] < 0: st.error(tr('保证金风险：可用权益小于零。模拟盘不执行真实交易所强平规则。','Margin alert: free margin below zero. The paper engine does not implement exchange liquidation rules.'))
            col=st.columns(4)
            side=col[0].selectbox(tr('方向','Side'),['BUY','SELL'],key='side')
            lots=col[1].number_input(tr('手数','Lots'),min_value=1,max_value=10000,value=1,step=1)
            otype=col[2].selectbox(tr('委托类型','Order type'),['MARKET','LIMIT'])
            limit=col[3].number_input(tr('限价','Limit price'),min_value=.01,value=float(obs),step=SPECS[m]['tick'],disabled=otype!='LIMIT')
            if st.button(tr('提交虚拟订单','Submit PAPER order'),type='primary',key='submit_order'):
                place(conn,m,mode,side,int(lots),otype,limit if otype=='LIMIT' else None,obs);st.success(tr('已加入云端待成交队列','Queued in cloud paper-account ledger'))
            if mode=='replay' and history is not None and len(history)>a['day_idx']+1:
                if st.button(tr('推进到下一交易日并执行订单','Advance ONE day and execute pending'),key='advance'):
                    i=int(a['day_idx'])+1;nextbar=history.iloc[i]
                    bar_dict={k:float(nextbar[k]) for k in ['open','high','low'] if k in nextbar and pd.notna(nextbar[k])}
                    if 'open' not in bar_dict:st.error(tr('缺少开盘价，不能保证无前视偏差','OPEN is missing: replay execution blocked to prevent lookahead bias'))
                    else:
                        result=execute(conn,m,mode,float(nextbar.close),str(nextbar.date.date()),margin,fee,bar_dict);set_index(conn,m,mode,i)
                        st.success(f"{tr('成交','Filled')}: {result['filled']} | {tr('拒单','Rejected')}: {result['rejected']}");st.rerun()
            if mode=='forward':
                if st.button(tr('确认新观察价并撮合待成交订单','Confirm NEW observed quote and process pending'),key='mark_forward'):
                    if len(obsdate.strip())<10:st.error(tr('请填写报价时间及来源，防止误用假行情','Enter timestamp and source for observed market quote'))
                    else:
                        execute(conn,m,mode,float(obs),obsdate,margin,fee);st.rerun()
        open_orders=rows(conn,'orders',m,mode);valuations=rows(conn,'valuations',m,mode)
        st.markdown('#### '+tr('委托与成交记录','Order and fill journal'))
        if not open_orders.empty:
            st.dataframe(open_orders,hide_index=True,use_container_width=True)
            pending_ids=open_orders.loc[open_orders.status=='PENDING','id'].tolist()
            if pending_ids:
                cancel_id=st.selectbox(tr('选择撤销订单','Select pending order to cancel'),pending_ids,key=f'cancel_{m}_{mode}')
                if st.button(tr('撤销选中委托','Cancel selected order'),key=f'cancelbtn_{m}_{mode}'):
                    if cancel_order(conn,m,mode,cancel_id):st.rerun()
            st.download_button(tr('下载成交日志CSV','Download order journal'),open_orders.to_csv(index=False).encode('utf-8-sig'),file_name=f'{m}_{mode}_orders.csv')
        if not valuations.empty:
            st.markdown('#### '+tr('权益变化','Equity history'))
            st.line_chart(valuations.set_index('observation_date')[['equity']]);st.download_button(tr('下载净值历史','Download equity marks'),valuations.to_csv(index=False).encode('utf-8-sig'),file_name=f'{m}_{mode}_equity.csv')
        conn.close()
with tabs[5]:
    st.subheader(tr('历史策略回测：均线交叉','SMA crossover historical strategy backtest'))
    if not data:st.info(tr('需要先加载真实历史价格','Load actual historical prices first'))
    else:
        m=st.selectbox(tr('市场','Market'),list(data),format_func=lambda k:NAMES[k],key='bt_market')
        c=st.columns(5)
        ma_short=c[0].number_input(tr('短均线','Fast MA'),min_value=2,max_value=100,value=20)
        ma_long=c[1].number_input(tr('长均线','Slow MA'),min_value=3,max_value=250,value=60)
        bt_cap=c[2].number_input(tr('初始资金','Capital'),min_value=1000.,value=1000000. if m=='SHFE' else 200000.,step=1000.,key='btcap')
        bt_fee=c[3].number_input(tr('单边手续费/手','Fee / side / lot'),min_value=0.,value=10.,key='btfee')
        bt_slip=c[4].number_input(tr('单边滑点（跳）','Slippage ticks'),min_value=0,max_value=20,value=1)
        direction=st.radio(tr('策略方向','Strategy sides'),['both','long'],format_func=lambda x:tr('多空双向','Long and short') if x=='both' else tr('仅做多','Long only'),horizontal=True)
        if st.button(tr('运行历史回测','Run historical backtest'),key='run_bt'):
            try:
                curve,fills,stats=ma_crossover(data[m],m,short=ma_short,long=ma_long,initial=bt_cap,fee=bt_fee,slippage_ticks=bt_slip,side_mode=direction)
                st.session_state['backtest']=(curve,fills,stats,m)
            except Exception as e:st.error(f'{type(e).__name__}: {e}')
        bt=st.session_state.get('backtest')
        if bt:
            curve,fills,stats,btmarket=bt
            st.caption(f'{NAMES[btmarket]} | '+tr('信号在收盘确定，下一交易日开盘执行。','Signals at day close, executions at next-day open.'))
            cols=st.columns(4)
            for i,(label,val) in enumerate([(tr('总收益','Total return'),pct(stats['total_return'])),(tr('最大回撤','Max drawdown'),pct(stats['max_drawdown'])),(tr('成交次数','Executions'),str(stats['executions'])),(tr('期末权益','End equity'),fmt(stats['ending_equity']))]):cols[i].metric(label,val)
            st.line_chart(curve.set_index('date')[['equity']]);st.dataframe(fills,hide_index=True,use_container_width=True)
            st.download_button(tr('导出回测成交CSV','Export backtest fills'),fills.to_csv(index=False).encode('utf-8-sig'),file_name='strategy_backtest_fills.csv')
            st.caption(tr('简化模型：每次目标持仓为±1手；不计夜盘成交机制、涨跌停、交易所结算、实际换月和数据许可。','Simplified ±1-lot strategy; ignores actual rollover, night session, exchange clearing and delivery mechanics.'))
with tabs[6]:
    st.subheader(tr('外部模拟盘交易记录导入 / 对账','External simulation fills import / reconciliation'))
    st.info(tr('可使用SimNow或期货软件的导出CSV进行只读分析。不会登录外部账户，也不会代替你发送订单。','Import exported trade CSVs from SimNow or other futures terminals for read-only analysis. No login, API or order routing.'))
    extfile=st.file_uploader(tr('上传外部模拟成交记录CSV','Upload external paper fills CSV'),type=['csv'],key='external_csv')
    if extfile is not None:
        try:
            b=extfile.getvalue();ext=None
            for enc in ['utf-8-sig','gb18030','utf-16']:
                try:ext=pd.read_csv(pd.io.common.BytesIO(b),encoding=enc);break
                except UnicodeError:pass
            if ext is None:raise ValueError('Unable to decode CSV')
            st.caption(tr('原始导入数据（只读，不自动视为本系统真实成交）','Raw import (read-only; never counted as local fills automatically)'))
            st.dataframe(ext.head(500),use_container_width=True,hide_index=True)
            st.write(tr('字段映射提示：成交日期、合约、买卖、手数、成交价、手续费。','Recommended columns: trade datetime, symbol, side, lots, fill price, fees.'))
            st.download_button(tr('导出标准字段模板','Download normalized schema template'),pd.DataFrame(columns=['trade_datetime','symbol','side','lots','fill_price','fees','external_order_id']).to_csv(index=False).encode('utf-8-sig'),file_name='external_fills_template.csv')
        except Exception as e:st.error(str(e))
    st.markdown(tr('**真实模拟盘参考：** [上期所 SimNow 指南](https://edu.shfe.com.cn/home/simulate/simnow.html) · [SimNow 官网](https://www.simnow.com.cn/)','**Supported external reference:** [SHFE SimNow guide](https://edu.shfe.com.cn/home/simulate/simnow.html) · [SimNow website](https://www.simnow.com.cn/)'))
st.divider()
st.caption(tr('数据来源：SHFE主连为第三方公开行情；LME 3M第三方参考价需核对授权及报价定义。所有模拟成交仅为云端纸面交易，不构成投资建议。','Data: third-party public SHFE continuous series and third-party LME 3M reference (verify quote definitions/licensing). All fills are cloud paper simulations; not investment advice.'))
