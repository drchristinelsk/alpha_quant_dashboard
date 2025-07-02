# strategies/tsla_5min_sma.py

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

import threading
import time
import datetime
import pandas as pd
import os
from collections import deque

SYMBOL = "TSLA"
DATA_PATH = os.path.join("data", f"{SYMBOL.lower()}_5min_trades.csv")

class TSLA5MinSMATrader(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.prices = deque(maxlen=15)
        self.sma_15 = None
        self.current_price = None
        self.order_id = 0
        self.position = "NONE"
        self.trade_log = []
        self.last_trade_time = None
        self.last_trade_price = None
        os.makedirs("data", exist_ok=True)

    def nextValidId(self, orderId):
        self.order_id = orderId
        self.subscribe_realtime_bars()

    def subscribe_realtime_bars(self):
        contract = self.get_contract()
        self.reqRealTimeBars(1, contract, 300, "TRADES", False, [])

    def realtimeBar(self, reqId, time_unix, open_, high, low, close, volume, wap, count):
        self.current_price = close
        self.prices.append(close)

        if len(self.prices) == 15:
            self.sma_15 = sum(self.prices) / 15
            self.evaluate_trade_logic()

    def evaluate_trade_logic(self):
        if self.current_price is None or self.sma_15 is None:
            return

        cooldown_expired = (
            not self.last_trade_time or
            (datetime.datetime.now() - self.last_trade_time).total_seconds() > 300
        )

        if not cooldown_expired:
            return

        price_changed = (
            self.last_trade_price is None or
            abs(self.current_price - self.last_trade_price) > 0.1
        )

        if not price_changed:
            return

        if self.position == "NONE":
            if self.current_price > self.sma_15:
                self.place_market_order("BUY", 1)
                self.position = "LONG"
            else:
                self.place_market_order("SELL", 1)
                self.position = "SHORT"

        elif self.position == "LONG" and self.current_price < self.sma_15:
            self.place_market_order("SELL", 2)
            self.position = "SHORT"

        elif self.position == "SHORT" and self.current_price > self.sma_15:
            self.place_market_order("BUY", 2)
            self.position = "LONG"

    def place_market_order(self, action, qty):
        contract = self.get_contract()
        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = int(qty)
        order.eTradeOnly = False
        order.firmQuoteOnly = False

        self.placeOrder(self.order_id, contract, order)
        self.order_id += 1

        pnl = 0.0
        if self.last_trade_price:
            if action == "BUY":
                pnl = round(self.last_trade_price - self.current_price, 2)
            else:
                pnl = round(self.current_price - self.last_trade_price, 2)

        duration = 0
        if self.last_trade_time:
            duration = (datetime.datetime.now() - self.last_trade_time).total_seconds()

        trade = {
            "timestamp": pd.Timestamp.now(),
            "symbol": SYMBOL,
            "action": action,
            "price": self.current_price,
            "sma_15": self.sma_15,
            "pnl": pnl,
            "duration": duration
        }

        self.trade_log.append(trade)
        self.last_trade_time = datetime.datetime.now()
        self.last_trade_price = self.current_price

    def get_contract(self):
        c = Contract()
        c.symbol = SYMBOL
        c.secType = "STK"
        c.exchange = "SMART"
        c.currency = "USD"
        return c

    def run_bot(self):
        self.connect("127.0.0.1", 7497, clientId=12)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

        # Wait for at least one trade event
        timeout = time.time() + 600  # 10 minutes
        while time.time() < timeout:
            time.sleep(1)
            if self.trade_log:
                break

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

# ✅ Streamlit-compatible wrapper
class Strategy:
    def run(self):
        trader = TSLA5MinSMATrader()
        past_trades = trader.get_trade_log()
        flag = "RUNNING_TSLA_5MIN_SMA"
        if os.getenv(flag, "0") == "1":
            trader.run_bot()
            past_trades = trader.get_trade_log()
        return past_trades
