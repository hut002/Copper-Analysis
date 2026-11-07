"""Transparent scenario-based copper hedging calculations. No synthetic market quotes."""
from datetime import date
import math
import numpy as np
import pandas as pd

LOT_SIZES = {'SHFE': 5.0, 'LME_3M': 25.0}
CURRENCIES = {'SHFE': 'CNY', 'LME_3M': 'USD'}

def contract_quantity(market, exposure_tons, hedge_ratio):
    if market not in LOT_SIZES: raise ValueError('Unknown market')
    if exposure_tons < 0 or not 0 <= hedge_ratio <= 1: raise ValueError('Invalid exposure or ratio')
    size = LOT_SIZES[market]
    lots = math.floor(exposure_tons * hedge_ratio / size + 0.5)
    return {'lots': lots, 'contract_size': size, 'hedged_tons': lots*size,
            'effective_ratio': (lots*size/exposure_tons if exposure_tons else 0),
            'unhedged_tons': exposure_tons-lots*size}

def scenario_table(market, exposure, kind, reference_spot, entry_futures, hedge_ratio,
                   scenarios, hedge_beta=1.0, future_basis_change=0., fees_per_lot=0.,
                   fx=1., margin_rate=0.12):
    """Kind=inventory / future_purchase; all price inputs in native currency per tonne.
    Physical price P&L relative to reference; future exit = entry + beta*spot_move + basis_change.
    This is a sensitivity model, not a forecast of basis or executable quotes.
    """
    for x in [exposure, reference_spot, entry_futures, hedge_beta, fx]:
        if not np.isfinite(x): raise ValueError('Non-finite input')
    if reference_spot <= 0 or entry_futures <= 0 or fx <= 0: raise ValueError('Positive prices and FX required')
    if not 0 <= margin_rate <= 1: raise ValueError('Invalid margin')
    if not 0 <= hedge_beta <= 3: raise ValueError('Invalid hedge beta')
    if kind not in ('inventory','future_purchase'): raise ValueError('Invalid physical exposure')
    size=contract_quantity(market,exposure,hedge_ratio)
    physical_sign = 1 if kind=='inventory' else -1
    hedge_sign = -physical_sign
    units=size['hedged_tons']; lots=size['lots']
    out=[]
    for p in scenarios:
        if p <= 0: continue
        physical=(p-reference_spot)*exposure*physical_sign
        exit_fut=entry_futures + hedge_beta*(p-reference_spot) + future_basis_change
        fut=(exit_fut-entry_futures)*units*hedge_sign
        fees=lots*fees_per_lot
        out.append({'Scenario spot':float(p),'Scenario futures exit':float(exit_fut),
                    'Physical P&L':float(physical),'Futures P&L':float(fut),
                    'Trading costs':float(fees),'Hedged net P&L':float(physical+fut-fees),
                    'Unhedged P&L':float(physical),
                    'Hedged net (report currency)':float((physical+fut-fees)*fx)})
    return pd.DataFrame(out), {**size,'direction':('SELL futures' if kind=='inventory' else 'BUY futures'),
          'currency':CURRENCIES[market], 'initial_margin':float(entry_futures*units*margin_rate),
          'notional':float(entry_futures*units), 'contract_fees':float(lots*fees_per_lot)}

def maturity_table(today, exposure_date, month_quotes, market, volume_tons, ratio):
    rows=[]
    for months,quote in month_quotes.items():
        prompt=pd.Timestamp(today)+pd.DateOffset(months=int(months))
        maturity_days=(pd.Timestamp(exposure_date)-prompt).days
        q=contract_quantity(market,volume_tons,ratio)
        rows.append({'Tenor':f'{months}M','Indicative prompt':prompt.date().isoformat(),
                     'Entered futures quote':float(quote) if quote and quote>0 else None,
                     'Currency':CURRENCIES[market], 'Lots':q['lots'],
                     'Tenor fit':('Before exposure date — roll/adjust required' if maturity_days > 7 else 'After exposure date — close early' if maturity_days < -7 else 'Near exposure date')})
    return pd.DataFrame(rows)
