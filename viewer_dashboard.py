# viewer_dashboard.py

import streamlit as st
import pandas as pd
import os
from utils.performance_metrics import calculate_metrics

# Set Streamlit config
st.set_page_config(page_title="Alpha Quant Viewer", layout="wide")
st.title("📊 Alpha Quant Capital - Viewer Only Dashboard")
st.sidebar.header("🧠 Strategy Summary Viewer")

# Configuration
DATA_FOLDER = "data"

# List available trade logs
available_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith("_trades.csv")]

if not available_files:
    st.warning("No trade log files found in /data. Upload trade data to view performance.")
    st.stop()

# Select strategies to view
selected_files = st.sidebar.multiselect("Select Strategy Logs to View:", available_files, default=available_files)

summary_data = {}

for filename in selected_files:
    strategy_name = filename.replace("_trades.csv", "")
    filepath = os.path.join(DATA_FOLDER, filename)
    df = pd.read_csv(filepath, parse_dates=["timestamp"])

    if df.empty or "pnl" not in df.columns:
        continue

    metrics = calculate_metrics(df)
    summary_data[strategy_name] = metrics

# Show performance table
if summary_data:
    st.subheader("📋 Performance Summary")
    df_summary = pd.DataFrame.from_dict(summary_data, orient="index")
    df_summary.index.name = "Strategy"
    st.dataframe(df_summary.reset_index(), use_container_width=True)

    # Show expanders
    for filename in selected_files:
        strategy_name = filename.replace("_trades.csv", "")
        filepath = os.path.join(DATA_FOLDER, filename)
        df = pd.read_csv(filepath, parse_dates=["timestamp"])

        with st.expander(f"📂 Detailed View: {strategy_name}"):
            st.write("### Trade Log")
            st.dataframe(df, use_container_width=True)

            if "pnl" in df.columns and not df.empty:
                st.write("### Equity Curve")
                df['cumulative_pnl'] = df['pnl'].cumsum()
                st.line_chart(df.set_index("timestamp")["cumulative_pnl"])

                st.write("### Drawdown Curve")
                df['drawdown'] = df['cumulative_pnl'].cummax() - df['cumulative_pnl']
                st.area_chart(df.set_index("timestamp")["drawdown"])

                st.write("### Metrics")
                metrics = calculate_metrics(df)
                st.json(metrics)
else:
    st.info("No trade data available to analyze.")
