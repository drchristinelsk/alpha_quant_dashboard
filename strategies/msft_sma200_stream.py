# strategies/msft_sma200_stream.py

import pandas as pd
import os
import time
import datetime
import threading
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

SYMBOL = "MSFT"
DATA_PATH = os.path.join("data", f"{SYMBOL.lower()}_sma200_trades.csv")

class MSFTSMA200Trader(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.historical_data = []
        self.sma_200 = 0.0
        self.current_price = 0.0
        self.order_id = 0
        self.position = "NONE"
        self.sma_ready = False
        self.trade_log = []
        self.last_trade_time = None
        self.last_trade_price = None
        os.makedirs("data", exist_ok=True)

    def nextValidId(self, orderId):
        self.order_id = orderId
        self.request_historical_data()

    def request_historical_data(self):
        contract = self.get_contract()
        self.reqHistoricalData(
            1, contract, '', '300 D', '1 day', 'MIDPOINT', 0, 1, False, []
        )

    def historicalData(self, reqId, bar):
        self.historical_data.append(bar.close)

    def historicalDataEnd(self, reqId, start, end):
        if len(self.historical_data) >= 200:
            df = pd.Series(self.historical_data)
            self.sma_200 = df[-200:].mean()
            self.sma_ready = True
            self.subscribe_market_data()

    def subscribe_market_data(self):
        contract = self.get_contract()
        self.reqMktData(2, contract, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 4 and price > 0:  # Last price
            self.current_price = price
            if self.sma_ready:
                self.evaluate_trade_logic()

    def evaluate_trade_logic(self):
        if self.current_price == 0.0:
            return

        cooldown_expired = (
            not self.last_trade_time or
            (datetime.datetime.now() - self.last_trade_time).total_seconds() > 300
        )

        price_changed = (
            self.last_trade_price is None or
            abs(self.current_price - self.last_trade_price) > 0.1
        )

        if not cooldown_expired or not price_changed:
            return

        if self.position == "NONE":
            if self.current_price > self.sma_200:
                self.execute_trade("BUY")
                self.position = "LONG"
            elif self.current_price < self.sma_200:
                self.execute_trade("SELL")
                self.position = "SHORT"

        elif self.position == "LONG" and self.current_price < self.sma_200:
            self.execute_trade("SELL")
            self.position = "SHORT"

        elif self.position == "SHORT" and self.current_price > self.sma_200:
            self.execute_trade("BUY")
            self.position = "LONG"

    def execute_trade(self, action):
        contract = self.get_contract()
        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = 1
        order.eTradeOnly = False
        order.firmQuoteOnly = False

        self.placeOrder(self.order_id, contract, order)
        self.order_id += 1

        pnl = 0.0
        if self.last_trade_price:
            if action == "BUY":
                pnl = round(self.last_trade_price - self.current_price, 2)
            elif action == "SELL":
                pnl = round(self.current_price - self.last_trade_price, 2)

        duration = 0
        if self.last_trade_time:
            duration = (datetime.datetime.now() - self.last_trade_time).total_seconds()

        trade = {
            "timestamp": pd.Timestamp.now(),
            "symbol": SYMBOL,
            "action": action,
            "price": self.current_price,
            "sma_200": self.sma_200,
            "pnl": pnl,
            "duration": duration
        }

        self.trade_log.append(trade)
        self.last_trade_price = self.current_price
        self.last_trade_time = datetime.datetime.now()

    def get_contract(self):
        contract = Contract()
        contract.symbol = SYMBOL
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def run_bot(self):
        self.connect("127.0.0.1", 7497, clientId=13)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

        while not self.sma_ready:
            time.sleep(1)

        # Let it run just long enough to place a trade
        time.sleep(30)
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
            return pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
        return pd.DataFrame()

# ✅ Streamlit wrapper
class Strategy:
    def run(self):
        trader = MSFTSMA200Trader()
        past_trades = trader.get_trade_log()
        flag = "RUNNING_MSFT_SMA200"
        if os.getenv(flag, "0") == "1":
            trader.run_bot()
            past_trades = trader.get_trade_log()
        return past_trades
