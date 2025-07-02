import pandas as pd
import os
import datetime
import math

DATA_PATH = os.path.join("data", "spx_bull_put_trades.csv")

class SPXBullPutTrader:
    def __init__(self):
        self.trade_log = []
        os.makedirs("data", exist_ok=True)
        self.cooldown_minutes = 1440  # 1 trade per day
        self.last_trade_time = None

    def already_traded_today(self):
        if os.path.exists(DATA_PATH):
            df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
            if not df.empty:
                last_trade_time = df["timestamp"].max()
                return (datetime.now() - last_trade_time).total_seconds() < self.cooldown_minutes * 60
        return False

    def run(self):
        from ib_insync import IB, Index, Option, ComboLeg, Bag, LimitOrder

        # 🛑 Skip weekends
        if datetime.today().weekday() >= 5:
            print("📅 Weekend detected — skipping trade.")
            return pd.DataFrame()

        if self.already_traded_today():
            print("⏳ Cooldown active — already traded today.")
            return pd.DataFrame()

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
            print("⚠️ No same-day expiration available.")
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

        # ❌ Prevent duplicate spread
        if self.trade_exists(sell_strike, buy_strike):
            print("🔁 Identical trade already exists — skipping.")
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

        credit = round(sell_price - buy_price, 2)
        order = LimitOrder(action='SELL', totalQuantity=1, lmtPrice=credit)

        try:
            trade = ib.placeOrder(spread, order)
            ib.sleep(2)
            status = trade.orderStatus.status
        except Exception as e:
            ib.disconnect()
            return pd.DataFrame()

        duration = 0
        if self.last_trade_time:
            duration = (datetime.datetime.now() - self.last_trade_time).total_seconds()

        self.trade_log.append({
            'timestamp': pd.Timestamp.now(),
            'symbol': 'SPX',
            'action': 'SELL PUT SPREAD',
            'sell_strike': sell_strike,
            'buy_strike': buy_strike,
            'credit': credit,
            'status': status,
            'pnl': 0.0,  # 💡 Extend later to calculate at expiry
            'duration': duration
        })

        self.last_trade_time = datetime.datetime.now()

        ib.disconnect()
        return pd.DataFrame(self.trade_log)

    def trade_exists(self, sell_strike, buy_strike):
        if os.path.exists(DATA_PATH):
            df = pd.read_csv(DATA_PATH)
            today_str = datetime.now().strftime("%Y-%m-%d")
            df_today = df[df["timestamp"].str.startswith(today_str)]
            return not df_today[
                (df_today["sell_strike"] == sell_strike) &
                (df_today["buy_strike"] == buy_strike)
            ].empty
        return False

    def save_trades(self):
        if self.trade_log:
            df = pd.DataFrame(self.trade_log)
            if os.path.exists(DATA_PATH):
                existing = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
                df = pd.concat([existing, df], ignore_index=True)
                df = df.drop_duplicates(subset=["timestamp", "sell_strike", "buy_strike"])
            df.to_csv(DATA_PATH, index=False)

    def get_trade_log(self):
        if os.path.exists(DATA_PATH):
            return pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
        return pd.DataFrame()


# ✅ Streamlit-compatible wrapper
class Strategy:
    def run(self):
        trader = SPXBullPutTrader()
        past_trades = trader.get_trade_log()
        flag = "RUNNING_SPX_BULL_PUT_STRATEGY"
        if os.getenv(flag, "0") == "1":
            trader.run()
            trader.save_trades()
            past_trades = trader.get_trade_log()
        return past_trades
