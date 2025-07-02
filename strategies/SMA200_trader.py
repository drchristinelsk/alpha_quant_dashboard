import pandas as pd
import os
import time
import datetime
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading

DATA_PATH = os.path.join("data", "sma200_trades.csv")

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
        self.last_trade_time = None
        self.is_connected = False
        os.makedirs("data", exist_ok=True)

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
            self.infer_last_position()
            self.subscribe_market_data()

    def subscribe_market_data(self):
        contract = self.get_msft_contract()
        self.reqMktData(2, contract, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 4 and price > 0:
            self.current_price = price
            if self.sma_ready:
                self.evaluate_trade_logic()

    def evaluate_trade_logic(self):
        if self.current_price == 0.0:
            return

        action = None
        if self.position == "NONE":
            if self.current_price > self.sma_200:
                action = "BUY"
            elif self.current_price < self.sma_200:
                action = "SELL"
        elif self.position == "LONG" and self.current_price < self.sma_200:
            action = "SELL"
        elif self.position == "SHORT" and self.current_price > self.sma_200:
            action = "BUY"

        if action and self.should_trade(action):
            self.execute_trade(action)

    def should_trade(self, action):
        now = datetime.datetime.now()

        # Cooldown check (5 minutes)
        if self.last_trade_time and (now - self.last_trade_time).total_seconds() < 300:
            print("⏳ Cooldown active.")
            return False

        # Duplicate action + price check
        if self.trade_log and self.trade_log[-1]["action"] == action:
            last_price = self.trade_log[-1]["price"]
            price_diff = abs(self.current_price - last_price)
            if last_price > 0 and price_diff / last_price < 0.005:
                print("⚠️ Price change too small. Skipping duplicate trade.")
                return False

        return True

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

        duration = 0
        if self.last_trade_time:
            duration = (datetime.datetime.now() - self.last_trade_time).total_seconds()

        # Calculate PnL before appending trade
        pnl = self.calculate_pnl(action)

        self.trade_log.append({
            "timestamp": pd.Timestamp.now(),
            "action": action,
            "price": self.current_price,
            "sma_200": self.sma_200,
            "pnl": pnl,
            "duration": duration
        })

        self.position = "LONG" if action == "BUY" else "SHORT"
        self.last_trade_time = datetime.datetime.now()

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

    def infer_last_position(self):
        if os.path.exists(DATA_PATH):
            df = pd.read_csv(DATA_PATH)
            if not df.empty and "action" in df.columns:
                last_action = df.iloc[-1]["action"]
                self.position = "LONG" if last_action == "BUY" else "SHORT"
        else:
            self.position = "NONE"

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

        while not self.is_connected or not self.sma_ready:
            time.sleep(1)

        if self.sma_ready and self.current_price > 0:
            self.evaluate_trade_logic()
            self.save_trades()

        self.disconnect()

    def save_trades(self):
        if self.trade_log:
            df = pd.DataFrame(self.trade_log)
            if os.path.exists(DATA_PATH):
                existing = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
                df = pd.concat([existing, df], ignore_index=True)
                df = df.drop_duplicates(subset=["timestamp", "action", "price"])
            df.to_csv(DATA_PATH, index=False)

    def get_trade_log(self):
        if os.path.exists(DATA_PATH):
            return pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
        return pd.DataFrame()


class Strategy:
    def run(self):
        trader = SMA200Trader()
        past_trades = trader.get_trade_log()
        flag = "RUNNING_SMA200_TRADER"
        if os.getenv(flag, "0") == "1":
            trader.run_bot()
            past_trades = trader.get_trade_log()
        return past_trades


def main():
    trader = SMA200Trader()
    trader.run_bot()

if __name__ == "__main__":
    main()
