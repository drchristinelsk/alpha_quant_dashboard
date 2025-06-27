# strategies/spx_bull_put_strategy.py

import pandas as pd
from datetime import datetime
import math

class SPXBullPutTrader:
    def __init__(self):
        self.trade_log = []

    def run(self):
        # ⛔ Delay import until now to avoid event loop error
        from ib_insync import IB, Index, Option, ComboLeg, Bag, LimitOrder

        ib = IB()
        try:
            ib.connect('127.0.0.1', 7497, clientId=4)
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            return pd.DataFrame()

        symbol = 'SPX'
        index = Index(symbol, 'CBOE', 'USD')
        ib.qualifyContracts(index)

        ticker = ib.reqMktData(index, '', False, False)
        ib.sleep(2)
        open_price = ticker.open or ticker.last or ticker.close or 5000.0
        target_sell_price = open_price * 0.99

        try:
            chains = ib.reqSecDefOptParams(index.symbol, '', index.secType, index.conId)
            chain = next(c for c in chains if c.exchange == 'CBOE')
        except Exception as e:
            ib.disconnect()
            return pd.DataFrame()

        today = datetime.today().strftime("%Y%m%d")
        if today not in chain.expirations:
            ib.disconnect()
            return pd.DataFrame()

        expiry = today
        strikes = sorted([s for s in chain.strikes if target_sell_price - 50 <= s <= target_sell_price + 50])
        if not strikes:
            ib.disconnect()
            return pd.DataFrame()

        sell_strike = max([s for s in strikes if s <= target_sell_price], default=min(strikes))
        buy_strike = sell_strike - 5
        if buy_strike not in strikes:
            ib.disconnect()
            return pd.DataFrame()

        sell_put = Option(symbol, expiry, sell_strike, 'P', 'CBOE')
        buy_put = Option(symbol, expiry, buy_strike, 'P', 'CBOE')
        ib.qualifyContracts(sell_put, buy_put)

        sell_ticker = ib.reqMktData(sell_put, '', False, False)
        buy_ticker = ib.reqMktData(buy_put, '', False, False)
        ib.sleep(3)

        sell_price = sell_ticker.marketPrice() or sell_ticker.last or sell_ticker.bid
        buy_price = buy_ticker.marketPrice() or buy_ticker.last or buy_ticker.bid
        if math.isnan(sell_price) or math.isnan(buy_price):
            ib.disconnect()
            return pd.DataFrame()

        spread = Bag(
            symbol=symbol,
            exchange='CBOE',
            currency='USD',
            comboLegs=[
                ComboLeg(conId=sell_put.conId, ratio=1, action='SELL', exchange='CBOE'),
                ComboLeg(conId=buy_put.conId, ratio=1, action='BUY', exchange='CBOE')
            ]
        )

        order = LimitOrder(
            action='SELL',
            totalQuantity=1,
            lmtPrice=0.50
        )

        try:
            trade = ib.placeOrder(spread, order)
            ib.sleep(1)
            status = trade.orderStatus.status
        except Exception as e:
            ib.disconnect()
            return pd.DataFrame()

        self.trade_log.append({
            'timestamp': pd.Timestamp.now(),
            'symbol': 'SPX',
            'action': 'SELL PUT SPREAD',
            'sell_strike': sell_strike,
            'buy_strike': buy_strike,
            'credit': 0.50,
            'status': status,
            'pnl': 0.0
        })

        ib.disconnect()
        return pd.DataFrame(self.trade_log)

# Streamlit-compatible wrapper
class Strategy:
    def run(self):
        bot = SPXBullPutTrader()
        df = bot.run()
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
