import pandas as pd
import time
import numpy as np
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading

class SMA200Trader(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.historical_data = []
        self.sma_200 = 0.0
        self.current_price = 0.0
        self.order_id = 0
        self.position = "NONE"
        self.sma_ready = False
        self.trade_log = []
        self.is_connected = False

    def nextValidId(self, orderId):
        self.order_id = orderId
        self.is_connected = True
        self.request_historical_data()
        self.reqAccountSummary(9001, "All", "AccountType,NetLiquidation,TotalCashValue")

    def accountSummary(self, reqId, account, tag, value, currency):
        pass  # Suppress print for dashboard use

    def request_historical_data(self):
        contract = self.get_msft_contract()
        self.reqHistoricalData(1, contract, '', '300 D', '1 day', 'MIDPOINT', 0, 1, False, [])

    def historicalData(self, reqId, bar):
        self.historical_data.append(bar.close)

    def historicalDataEnd(self, reqId, start, end):
        if len(self.historical_data) >= 200:
            df = pd.Series(self.historical_data)
            self.sma_200 = df[-200:].mean()
            self.sma_ready = True
            self.subscribe_market_data()

    def subscribe_market_data(self):
        contract = self.get_msft_contract()
        self.reqMktData(2, contract, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 4:  # Last Price
            self.current_price = price
            if self.sma_ready:
                self.evaluate_trade_logic()

    def evaluate_trade_logic(self):
        if self.position == "NONE":
            if self.current_price > self.sma_200:
                self.execute_trade("BUY")
            elif self.current_price < self.sma_200:
                self.execute_trade("SELL")
        elif self.position == "LONG" and self.current_price < self.sma_200:
            self.execute_trade("SELL")
        elif self.position == "SHORT" and self.current_price > self.sma_200:
            self.execute_trade("BUY")

    def execute_trade(self, action):
        contract = self.get_msft_contract()
        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = 1
        order.eTradeOnly = False
        order.firmQuoteOnly = False

        self.placeOrder(self.order_id, contract, order)
        self.order_id += 1

        pnl = self.calculate_pnl(action)
        self.trade_log.append({
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "action": action,
            "price": self.current_price,
            "sma_200": self.sma_200,
            "pnl": pnl,
        })

        self.position = "LONG" if action == "BUY" else "SHORT" # type: ignore
        self.order_id += 1

    def calculate_pnl(self, action):
        if not self.trade_log:
            return 0.0
        last_trade = self.trade_log[-1]
        prev_price = last_trade['price']
        if last_trade['action'] == "BUY" and action == "SELL":
            return self.current_price - prev_price
        elif last_trade['action'] == "SELL" and action == "BUY":
            return prev_price - self.current_price
        else:
            return 0.0

    def get_msft_contract(self):
        contract = Contract()
        contract.symbol = "MSFT"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract

    def run_bot(self):
        self.connect("127.0.0.1", 7497, clientId=2)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        time.sleep(10)  # Allow some data collection
        self.disconnect()

    def get_trade_log(self):
        return pd.DataFrame(self.trade_log)

# Streamlit-compatible wrapper
class Strategy:
    def run(self):
        bot = SMA200Trader()
        bot.run_bot()
        df = bot.get_trade_log()
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
