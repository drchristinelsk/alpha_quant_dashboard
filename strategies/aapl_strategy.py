# strategies/aapl_strategy.py

import pandas as pd
import os
import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading

DATA_PATH = os.path.join("data", "aapl_trades.csv")

class AAPLTrader(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []
        # self.order_id = 0
        self.done = False
        self.trade_log = []

    def nextValidId(self, orderId: int):
        self.order_id = orderId
        self.get_historical_data()

    def get_historical_data(self):
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        self.reqHistoricalData(
            reqId=1,
            contract=contract,
            endDateTime='',
            durationStr='300 D',
            barSizeSetting='1 day',
            whatToShow='MIDPOINT',
            useRTH=0,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[]
        )

    def historicalData(self, reqId: int, bar):
        self.data.append([bar.date, bar.close])

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        df = pd.DataFrame(self.data, columns=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df.dropna(inplace=True)

        sma_180 = df["close"].rolling(window=180).mean().iloc[-1]
        last_price = df["close"].iloc[-1]

        action = None
        pnl = 0.0

        if pd.notna(sma_180):
            if last_price > sma_180:
                action = "BUY"
            elif last_price < sma_180:
                action = "SELL"

        if action:
            contract = self.get_contract()
            order = Order()
            order.action = action
            order.orderType = "MKT"
            order.totalQuantity = 1
            order.eTradeOnly = False
            order.firmQuoteOnly = False
            self.placeOrder(self.order_id, contract, order)
            self.order_id += 1

            pnl = round((last_price - sma_180), 2) if action == "BUY" else round((sma_180 - last_price), 2)
            trade = {
                "timestamp": pd.Timestamp.now(),
                "symbol": "AAPL",
                "action": action,
                "price": last_price,
                "sma_180": sma_180,
                "pnl": pnl
            }
            self.trade_log.append(trade)

        self.done = True

    def get_contract(self):
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def run_bot(self):
        self.connect("127.0.0.1", 7497, clientId=3)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

        while not self.done:
            time.sleep(1)

        self.disconnect()

    def save_trades(self):
        if self.trade_log:
            df = pd.DataFrame(self.trade_log)
            if os.path.exists(DATA_PATH):
                existing = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
                df = pd.concat([existing, df], ignore_index=True)
            df.to_csv(DATA_PATH, index=False)

    def get_trade_log(self):
        if os.path.exists(DATA_PATH):
            return pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
        return pd.DataFrame()

# ✅ Streamlit-compatible Strategy wrapper
class Strategy:
    def run(self):
        trader = AAPLTrader()

        # Always return previous trades first
        past_trades = trader.get_trade_log()

        strategy_flag = f"RUNNING_{__name__.split('.')[-1].upper()}"
        if os.getenv(strategy_flag, "0") == "1":
            trader.run_bot()
            trader.save_trades()
            past_trades = trader.get_trade_log()

        return past_trades
