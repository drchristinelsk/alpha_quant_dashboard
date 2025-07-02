# strategies/mag7_sma_strategy.py

import os
import time
import threading
import pandas as pd
import datetime
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

# === Custom SMA Settings for Magnificent 7 ===
MAG7_SMA_SETTINGS = {
    "MSFT": 150,
    "AAPL": 130,
    "TSLA": 132,
    "NVDA": 155,
    "META": 125,
    "GOOGL": 140,
    "AMZN": 170
}

DATA_PATH = os.path.join("data", "mag7_trades.csv")
os.makedirs("data", exist_ok=True)

class Mag7CustomSMATrader(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.order_id = 0
        self.symbols = list(MAG7_SMA_SETTINGS.keys())
        self.current_symbol_index = 0
        self.symbol = self.symbols[0]
        self.data = []
        self.done = False
        self.trade_log = []
        self.last_trade_time = None

    def nextValidId(self, orderId: int):
        self.order_id = orderId
        self.request_next_symbol_data()

    def request_next_symbol_data(self):
        if self.current_symbol_index >= len(self.symbols):
            self.done = True
            return

        self.data = []
        self.symbol = self.symbols[self.current_symbol_index]

        contract = Contract()
        contract.symbol = self.symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.currency = "USD"

        sma_window = MAG7_SMA_SETTINGS[self.symbol]
        duration_str = f"{int(sma_window * 2)} D"

        self.reqHistoricalData(
            reqId=1,
            contract=contract,
            endDateTime='',
            durationStr=duration_str,
            barSizeSetting='1 day',
            whatToShow='TRADES',
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

        sma_window = MAG7_SMA_SETTINGS[self.symbol]
        if len(df) < sma_window:
            self.move_to_next()
            return

        sma_val = df["close"].rolling(window=sma_window).mean().iloc[-1]
        last_price = df["close"].iloc[-1]

        action = None
        if pd.notna(sma_val):
            if last_price > sma_val:
                action = "BUY"
            elif last_price < sma_val:
                action = "SELL"

        if action:
            self.place_market_order(self.symbol, action, last_price, sma_val)

        self.move_to_next()

    def place_market_order(self, symbol, action, price, sma_val):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.currency = "USD"

        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = 1
        order.eTradeOnly = False
        order.firmQuoteOnly = False

        self.placeOrder(self.order_id, contract, order)
        self.order_id += 1

        duration = 0
        if self.last_trade_time:
            duration = (datetime.datetime.now() - self.last_trade_time).total_seconds()

        pnl = round(abs(price - sma_val), 2)
        self.trade_log.append({
            "timestamp": pd.Timestamp.now(),
            "symbol": symbol,
            "action": action,
            "price": price,
            "sma": sma_val,
            "pnl": pnl,
            "duration": duration
        })

        self.last_trade_time = datetime.datetime.now()

    def move_to_next(self):
        self.current_symbol_index += 1
        time.sleep(2)
        self.request_next_symbol_data()

    def run_bot(self):
        self.connect("127.0.0.1", 7497, clientId=8)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

        while not self.done:
            time.sleep(1)

        self.save_trades()
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
            df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
            df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
            return df
        return pd.DataFrame()

# ✅ Wrapper for Streamlit
class Strategy:
    def run(self):
        trader = Mag7CustomSMATrader()
        past_trades = trader.get_trade_log()
        flag = "RUNNING_MAG7_SMA"
        if os.getenv(flag, "0") == "1":
            trader.run_bot()
            past_trades = trader.get_trade_log()
        return past_trades
