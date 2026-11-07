# -*- coding: utf-8 -*-
"""SHFE copper main continuous + LME copper three-month benchmark, 3y quant analysis.
Uses real prices only; no fabricated market observations. Python >=3.10.
"""
import argparse, json, traceback, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FIELD_MAP = {
    '日期':'date','交易日期':'date','时间':'date','Date':'date','date':'date',
    '开盘':'open','开盘价':'open','open':'open','Open':'open',
    '最高':'high','最高价':'high','high':'high','High':'high',
    '最低':'low','最低价':'low','low':'low','Low':'low',
    '收盘':'close','收盘价':'close','close':'close','Close':'close','最新价':'close',
    '成交量':'volume','volume':'volume','Volume':'volume',
    '持仓量':'open_interest','open_interest':'open_interest','持仓':'open_interest',
    'three_month':'close','3_month':'close','结算价':'settle',
}

def normalize(raw, start, end, label):
    if raw is None or raw.empty: raise ValueError(f'{label}: 行情为空')
    df=raw.copy()
    df.columns=[FIELD_MAP.get(str(c).strip(),str(c).strip()) for c in df.columns]
    df=df.loc[:,~df.columns.duplicated(keep='first')]
    if 'date' not in df or 'close' not in df:
        raise ValueError(f'{label}: 日期/收盘价字段无法识别，实际字段: {list(raw.columns)}')
    df['date']=pd.to_datetime(df['date'],errors='coerce')
    if df['date'].dt.tz is not None: df['date']=df['date'].dt.tz_localize(None)
    for c in ['open','high','low','close','volume','open_interest']:
        if c in df:
            df[c]=pd.to_numeric(df[c].astype(str).str.replace(',','',regex=False) if df[c].dtype=='object' else df[c],errors='coerce')
    df=df.dropna(subset=['date','close'])
    df=df[df.close>0].sort_values('date').drop_duplicates('date',keep='last')
    df=df[(df.date>=pd.Timestamp(start))&(df.date<=pd.Timestamp(end))].reset_index(drop=True)
    if len(df)<500:
        raise ValueError(f'{label}: 有效日线仅 {len(df)} 行，不满足三年模型最少500行要求')
    if df.date.iloc[0]>pd.Timestamp(start)+pd.Timedelta(days=80):
        raise ValueError(f'{label}: 起点过晚 {df.date.iloc[0].date()}，可能不是完整的三年序列')
    if df.date.iloc[-1]<pd.Timestamp(end)-pd.Timedelta(days=12):
        raise ValueError(f'{label}: 数据停在 {df.date.iloc[-1].date()}，距查询截止日超12天；禁止误作最新数据')
    return df

def fetch_shfe(start,end,csv=None):
    if csv: return normalize(pd.read_csv(csv,encoding='utf-8-sig'),start,end,'SHFE CSV'),f'本地沪铜CSV: {csv}'
    import akshare as ak
    attempts=[]
    options=[('新浪 AKShare futures_main_sina(CU0)',lambda:ak.futures_main_sina(symbol='CU0',start_date=start.replace('-',''),end_date=end.replace('-',''))),
             ('东方财富 AKShare futures_hist_em(沪铜主连)',lambda:ak.futures_hist_em(symbol='沪铜主连',period='daily',start_date=start.replace('-',''),end_date=end.replace('-','')))]
    for origin,fn in options:
        try: return normalize(fn(),start,end,'SHFE'),origin
        except Exception as e: attempts.append(f'{origin}: {type(e).__name__}: {e}')
    raise RuntimeError('沪铜数据源全部失败\n'+'\n'.join(attempts))

def fetch_lme(start,end,csv=None):
    if csv: return normalize(pd.read_csv(csv,encoding='utf-8-sig'),start,end,'LME CSV'),f'本地LME 3M CSV: {csv}'
    attempts=[]
    try:
        import akshare as ak
        return normalize(ak.futures_foreign_hist(symbol='CAD'),start,end,'LME CAD'), '新浪 AKShare futures_foreign_hist(CAD)，第三方LME铜3个月行情（需核对报价定义）'
    except Exception as e: attempts.append(f'新浪LME CAD: {type(e).__name__}: {e}')
    try:
        url='https://raw.githubusercontent.com/c-harsha/lme/main/data/copper.csv'
        raw=pd.read_csv(url)
        return normalize(raw,start,end,'LME CSV'),f'公开汇编LME三个月参考价 CSV: {url}（非LME官方授权行情）'
    except Exception as e: attempts.append(f'公开LME CSV: {type(e).__name__}: {e}')
    raise RuntimeError('伦铜数据源全部失败\n'+'\n'.join(attempts))

def metrics_and_indicators(df):
    d=df.copy();p=d.close
    d['return']=p.pct_change();d['log_return']=np.log(p/p.shift(1))
    for n in (5,10,20,60,120,250):d[f'MA{n}']=p.rolling(n).mean()
    ema12=p.ewm(span=12,adjust=False).mean();ema26=p.ewm(span=26,adjust=False).mean()
    d['MACD']=ema12-ema26;d['MACD_signal']=d.MACD.ewm(span=9,adjust=False).mean();d['MACD_hist']=d.MACD-d.MACD_signal
    delta=p.diff();up=delta.clip(lower=0);down=(-delta.clip(upper=0))
    avgup=up.ewm(alpha=1/14,adjust=False,min_periods=14).mean();avgdown=down.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    d['RSI14']=100-100/(1+avgup/avgdown.replace(0,np.nan));d.loc[(avgdown==0)&(avgup>0),'RSI14']=100
    sd20=p.rolling(20).std();d['BOLL_upper']=d.MA20+2*sd20;d['BOLL_lower']=d.MA20-2*sd20
    for n in (20,60,120,250): d[f'vol{n}']=d.log_return.rolling(n).std()*np.sqrt(252)
    if {'high','low'}.issubset(d):
        tr=pd.concat([(d.high-d.low).abs(),(d.high-p.shift()).abs(),(d.low-p.shift()).abs()],axis=1).max(axis=1)
        d['ATR14']=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    d['wealth']=np.exp(d.log_return.fillna(0).cumsum());d['drawdown']=d.wealth/d.wealth.cummax()-1
    loss=-d['return'].dropna();r20=-(p/p.shift(20)-1).dropna()
    def tail(x,alpha):
        q=float(x.quantile(alpha));return {'VaR':q,'CVaR':float(x[x>=q].mean())}
    ix=int(d.drawdown.idxmin());peak=int(d.wealth.iloc[:ix+1].idxmax())
    stats={
        'period_start':str(d.date.iloc[0].date()),'period_end':str(d.date.iloc[-1].date()),'n_days':len(d),
        'last_price':float(p.iloc[-1]),'total_return':float(p.iloc[-1]/p.iloc[0]-1),
        'annualized_volatility_3y':float(d.log_return.std()*np.sqrt(252)),
        'volatility_20d':float(d.vol20.iloc[-1]),'volatility_60d':float(d.vol60.iloc[-1]),
        'volatility_120d':float(d.vol120.iloc[-1]),'volatility_250d':float(d.vol250.iloc[-1]),
        'historical_1d_95':tail(loss,.95),'historical_1d_99':tail(loss,.99),
        'historical_20d_95':tail(r20,.95),'historical_20d_99':tail(r20,.99),
        'max_drawdown':float(d.drawdown.min()),'max_dd_peak':str(d.date.iloc[peak].date()),'max_dd_trough':str(d.date.iloc[ix].date()),
        'RSI14':float(d.RSI14.iloc[-1]),'MACD':float(d.MACD.iloc[-1]),'MACD_signal':float(d.MACD_signal.iloc[-1]),
        'MA20':float(d.MA20.iloc[-1]),'MA60':float(d.MA60.iloc[-1]),'MA250':float(d.MA250.iloc[-1]),
        'abnormal_log_returns_over_12pct':int((d.log_return.abs()>.12).sum())}
    return d,stats

def monte_carlo(d,paths=30000,horizon=20,seed=20261105):
    r=d.log_return.dropna().to_numpy();last=float(d.close.iloc[-1]);rng=np.random.default_rng(seed)
    normal=r.mean()+r.std(ddof=1)*rng.standard_normal((paths,horizon))
    block=5;blocks=int(np.ceil(horizon/block));inds=rng.integers(0,len(r),size=(paths,blocks))
    boot=r[(inds[:,:,None]+np.arange(block)[None,None,:])%len(r)].reshape(paths,-1)[:,:horizon]
    summary={};curve=pd.DataFrame({'day':np.arange(horizon+1)})
    for name,rets in [('normal_log_returns',normal),('block_bootstrap',boot)]:
        arr=last*np.exp(np.cumsum(rets,axis=1));full=np.column_stack((np.full(paths,last),arr))
        q=(.01,.05,.25,.5,.75,.95,.99)
        summary[name]={'prices_day20':{f'p{int(x*100):02d}':float(np.quantile(arr[:,-1],x)) for x in q},
                        'prob_below_last':float((arr[:,-1]<last).mean()),
                        'prob_fall_5pct':float((arr[:,-1]<last*.95).mean())}
        for x in (.05,.5,.95):curve[f'{name}_p{int(x*100):02d}']=np.quantile(full,x,axis=0)
    return summary,curve

def chart(d,curve,out,title,unit):
    for name,y in [('price',d.close),('volatility',d.vol60*100),('drawdown',d.drawdown*100)]:
        fig,ax=plt.subplots(figsize=(11,4));ax.plot(d.date,y);ax.set_title(f'{title} {name} ({unit if name=="price" else "%"})');ax.grid(alpha=.25)
        fig.autofmt_xdate();fig.tight_layout();fig.savefig(out/f'{name}.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5));ax.fill_between(curve.day,curve.block_bootstrap_p05,curve.block_bootstrap_p95,alpha=.25,label='5%-95% bootstrap')
    ax.plot(curve.day,curve.block_bootstrap_p50,label='Bootstrap median');ax.plot(curve.day,curve.normal_log_returns_p50,'--',label='Normal median')
    ax.set_title(f'{title}: 20 trading day Monte Carlo ({unit})');ax.legend();ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(out/'monte_carlo_20d.png',dpi=150);plt.close(fig)

def export_market(df,origin,market,out,paths):
    o=out/market;o.mkdir(parents=True,exist_ok=True)
    d,stats=metrics_and_indicators(df);sim,curve=monte_carlo(d,paths=paths)
    d.to_csv(o/'daily_indicators.csv',index=False,encoding='utf-8-sig')
    curve.to_csv(o/'mc_quantiles.csv',index=False,encoding='utf-8-sig')
    stats['simulation']=sim;stats['source']=origin
    (o/'metrics.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    chart(d,curve,o,market,'CNY/ton' if market=='SHFE' else 'USD/ton')
    return d,stats

def crossmarket(a,b,out):
    # Compare same calendar dates only, no contemporaneous tradability assumed.
    x=a[['date','close']].rename(columns={'close':'shfe_cny_per_ton'}).merge(b[['date','close']].rename(columns={'close':'lme_usd_per_ton'}),on='date',how='inner')
    if len(x)<300:raise ValueError(f'跨市场共同交易日不足: {len(x)}')
    x['shfe_logret']=np.log(x.shfe_cny_per_ton/x.shfe_cny_per_ton.shift(1))
    x['lme_logret']=np.log(x.lme_usd_per_ton/x.lme_usd_per_ton.shift(1))
    x['return_corr_60d']=x.shfe_logret.rolling(60).corr(x.lme_logret)
    x['shfe_index100']=x.shfe_cny_per_ton/x.shfe_cny_per_ton.iloc[0]*100
    x['lme_index100']=x.lme_usd_per_ton/x.lme_usd_per_ton.iloc[0]*100
    x['shfe_over_lme_quote_ratio']=x.shfe_cny_per_ton/x.lme_usd_per_ton
    x.to_csv(out/'cross_market_comparison.csv',index=False,encoding='utf-8-sig')
    result={'overlap_days':len(x),'start':str(x.date.iloc[0].date()),'end':str(x.date.iloc[-1].date()),
            'same_date_daily_return_correlation':float(x[['shfe_logret','lme_logret']].corr().iloc[0,1]),
            'rolling_60d_correlation_last':float(x.return_corr_60d.iloc[-1]),
            'warning':'同日期收益率因中国与伦敦交易时段不同可能错位。报价比值不是进口套利利润；必须加USDCNY、增值税、运费、升贴水、关税、资金成本及交易时点调整。'}
    (out/'cross_market_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    fig,ax=plt.subplots(figsize=(11,4.5));ax.plot(x.date,x.shfe_index100,label='SHFE = 100');ax.plot(x.date,x.lme_index100,label='LME = 100');ax.legend();ax.grid(alpha=.25);ax.set_title('SHFE vs LME 3-month normalized close (first overlap = 100)')
    fig.tight_layout();fig.savefig(out/'cross_market_normalized.png',dpi=150);plt.close(fig)
    return result

def main():
    pa=argparse.ArgumentParser(description='沪铜 + LME铜3个月双市场量化模型')
    for arg,default in [('--start','2023-11-05'),('--end','2026-11-04'),('--out','results_dual')]:pa.add_argument(arg,default=default)
    pa.add_argument('--shfe-csv',default=None);pa.add_argument('--lme-csv',default=None)
    pa.add_argument('--paths',type=int,default=30000);a=pa.parse_args()
    out=Path(a.out);out.mkdir(exist_ok=True,parents=True);results={}; failures={};frames={}
    for market,loader in [('SHFE',lambda:fetch_shfe(a.start,a.end,a.shfe_csv)),('LME_3M',lambda:fetch_lme(a.start,a.end,a.lme_csv))]:
        print(f'\n===== {market}: 正在获取真实历史数据 =====',flush=True)
        try:
            df,origin=loader();frames[market],results[market]=export_market(df,origin,market,out,a.paths)
            print(f'{market} 成功: {len(df)}条，最后日期 {df.date.iloc[-1].date()}',flush=True)
        except Exception as e:
            failures[market]=f'{type(e).__name__}: {e}'
            print(f'{market} 失败: {failures[market]}',flush=True)
    if len(frames)==2:
        try:results['cross_market']=crossmarket(frames['SHFE'],frames['LME_3M'],out)
        except Exception as e:failures['cross_market']=str(e)
    report=['# 沪铜 + 伦铜三个月 量化分析报告','',f'目标数据窗口: {a.start} 至 {a.end}','',
            '价格口径: 沪铜主力连续 CNY/吨；伦铜LME三个月 USD/吨。来源为公开数据渠道，并非LME官方授权历史数据。','']
    for market in ('SHFE','LME_3M'):
        if market not in results:report.extend([f'## {market}: 获取失败',failures.get(market,''),'']);continue
        s=results[market];report.extend([f'## {market}',f'来源: {s["source"]}',f'实际区间 {s["period_start"]}—{s["period_end"]} / {s["n_days"]}个交易日','',
            '|指标|计算值|','|---|---:|',
            f'|最新收盘价|{s["last_price"]:,.2f}|',f'|三年年化波动率|{s["annualized_volatility_3y"]:.2%}|',
            f'|20日年化波动率|{s["volatility_20d"]:.2%}|',f'|60日年化波动率|{s["volatility_60d"]:.2%}|',
            f'|历史1日95% VaR|{s["historical_1d_95"]["VaR"]:.2%}|',f'|历史1日95% CVaR|{s["historical_1d_95"]["CVaR"]:.2%}|',
            f'|历史1日99% VaR|{s["historical_1d_99"]["VaR"]:.2%}|',f'|历史1日99% CVaR|{s["historical_1d_99"]["CVaR"]:.2%}|',
            f'|历史20日95% VaR|{s["historical_20d_95"]["VaR"]:.2%}|',f'|最大回撤|{s["max_drawdown"]:.2%}|',
            f'|RSI14|{s["RSI14"]:.2f}|','',
            '### 未来20交易日模拟分位数','',
            '|方法|p05|p50|p95|','|---|---:|---:|---:|'])
        for method,v in s['simulation'].items():
            q=v['prices_day20'];report.append(f'|{method}|{q["p05"]:,.2f}|{q["p50"]:,.2f}|{q["p95"]:,.2f}|')
        report.append('')
    if 'cross_market' in results:
        q=results['cross_market'];report.extend(['## 跨市场同日收益率相关性',f'重叠交易日: {q["overlap_days"]}; 日收益率相关: {q["same_date_daily_return_correlation"]:.3f}; 60日滚动相关: {q["rolling_60d_correlation_last"]:.3f}',''])
    report.extend(['## 风险提示','* 沪铜主力连续换月可能制造非经济跳空。','* LME三个月滚动基准并非固定合约到期持有策略。',
                   '* 中英交易时段不完全一致；同日相关不能直接解释为交易信号。',
                   '* 伦铜三个月人民币价格和跨市进口盈亏需要每日USD/CNY与增值税、关税、运费、交割升水及资金成本，此版本不虚构这些数据。',
                   '* 模拟使用历史收益分布，不保证未来；数据抓取未成功时绝不输出虚构结果。'])
    (out/'REPORT_CN.md').write_text('\n'.join(report),encoding='utf-8')
    (out/'run_status.json').write_text(json.dumps({'success':list(results),'failures':failures,'request_start':a.start,'request_end':a.end},ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n结果目录:',out.resolve());print('成功:',list(results));print('失败:',failures)
    if not frames:raise SystemExit(2)
if __name__=='__main__':main()
