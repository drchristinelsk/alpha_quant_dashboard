# Alpha Quant Viewer Dashboard

This is a **viewer-only** Streamlit dashboard designed for visualizing performance metrics, trade logs, and equity curves from strategies run using Interactive Brokers (IBKR).

> ⚠️ This version **does not connect to IBKR**. It is safe for deployment on Streamlit Cloud.

---

## 🚀 Features

* View trade logs from any strategy saved to `/data/*.csv`
* Sharpe ratio, Sortino ratio, win rate, profit factor, and more
* Equity and drawdown charts per strategy
* Interactive filters and expandable strategy views

---

## 📁 Folder Structure

```
alpha_quant_dashboard/
├── data/
│   ├── aapl_trades.csv
│   └── sma200_trades.csv
├── strategies/         ← (Optional, not used in viewer)
├── utils/
│   └── performance_metrics.py
├── viewer_dashboard.py ← ✅ Deployment entry point
├── requirements.txt
└── README.md
```

---

## 🌐 Deploy to Streamlit Cloud

1. Push your code to a **GitHub repository**
2. Go to [https://streamlit.io/cloud](https://streamlit.io/cloud) and sign in
3. Click **New App**
4. Select your GitHub repo and set:

   * **Main file:** `viewer_dashboard.py`
5. Click **Deploy**

---

## 📌 Requirements

Install dependencies locally (optional):

```bash
pip install -r requirements.txt
```

---

## 📦 Add More Trade Logs

Just drop any `*_trades.csv` file into the `/data` folder.
Each file should have:

* `timestamp`
* `pnl`
* (optional) `action`, `symbol`, `duration`

---

## 🧠 Built With

* [Streamlit](https://streamlit.io)
* [Pandas](https://pandas.pydata.org)
* \[IBKR-compatible format logs]

---

## 🛡 Disclaimer

This dashboard is for educational and analytical use only. It does not execute live trades and is not intended for financial advice.
