import streamlit as st
import pandas as pd
import os
import importlib.util
from utils.performance_metrics import calculate_metrics

# dashboard.py — at the very top
import asyncio
import threading

try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Configuration
STRATEGY_FOLDER = "strategies"

# Set Streamlit config
st.set_page_config(page_title="Alpha Quant Capital Dashboard", layout="wide")
st.title("\U0001F4CA Alpha Quant Capital Dashboard")
st.sidebar.header("\U0001F9E0 Strategy Control Panel")

# Utility: Load strategy classes dynamically from a folder
def load_strategies():
    strategies = {}
    for filename in os.listdir(STRATEGY_FOLDER):
        if filename.endswith(".py"):
            path = os.path.join(STRATEGY_FOLDER, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, path)

            if spec is None or spec.loader is None:
                print(f"⚠️ Skipping {filename}: cannot load module spec.")
                continue  # Skip to next file
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if not asyncio.get_event_loop_policy().get_event_loop().is_running():
                asyncio.set_event_loop(asyncio.new_event_loop())

            if hasattr(module, "Strategy"):
                strategies[module_name] = module.Strategy()
    return strategies

# Upload new strategy
uploaded_file = st.sidebar.file_uploader("Upload a Strategy File (.py)", type="py")
if uploaded_file:
    with open(os.path.join(STRATEGY_FOLDER, uploaded_file.name), "wb") as f:
        f.write(uploaded_file.getvalue())
    st.sidebar.success("Strategy uploaded. Please reload the page to activate it.")

# Load strategies
strategies = load_strategies()
selected_strategies = {}

# Strategy toggles
for name in strategies:
    selected = st.sidebar.toggle(f"Run {name}", value=False)
    selected_strategies[name] = selected

    # Generalized environment flag
    # env_var_name = f"RUNNING_{name.upper()}"
    env_var_name = f"RUNNING_{name.upper().replace('_STRATEGY', '')}"
    os.environ[env_var_name] = "1" if selected else "0"

# Store performance summary
summary_data = []

# Display results
strategy_dataframes = {}
for name, strategy in strategies.items():
    # strategy = strategies[name]
    df = strategy.run()
    strategy_dataframes[name] = df

    if df.empty or 'pnl' not in df.columns:
        continue

    metrics = calculate_metrics(df)
    summary_data.append({
            "Strategy": name,
            "Sharpe Ratio": round(metrics['sharpe'], 2),
            "Sortino Ratio": round(metrics['sortino'], 2),
            "Win Rate (%)": round(metrics['win_rate'], 2),
            "Wins": metrics['wins'],
            "Losses": metrics['losses'],
            "Closed P/L": round(metrics['closed_pl'], 2),
            "Avg Win": round(metrics['avg_win'], 2),
            "Avg Loss": round(metrics['avg_loss'], 2),
            "Profit Factor": round(metrics['profit_factor'], 2),
            "Max Drawdown": round(metrics['max_drawdown'], 2),
            "Avg Duration (s)": round(metrics['avg_trade_duration'], 2)
        })

# Show performance table
if summary_data:
    st.subheader("\U0001F4CB Performance Summary")
    summary_df = pd.DataFrame(summary_data)

    # Add interactive filters
    with st.expander("\U0001F50D Filter and Sort Options"):
        col1, col2 = st.columns(2)
        strategy_filter = col1.multiselect("Select Strategies", options=summary_df['Strategy'].unique(), default=summary_df['Strategy'].unique())
        sort_by = col2.selectbox("Sort by Metric", options=summary_df.columns[1:], index=0)
        ascending = col2.checkbox("Sort Ascending", value=False)

        filtered_df = summary_df[summary_df['Strategy'].isin(strategy_filter)]
        filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)

    st.dataframe(filtered_df, use_container_width=True)

    # Export option
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Summary as CSV", data=csv, file_name="strategy_performance_summary.csv", mime="text/csv")

    # Expandable details
    for name, df in strategy_dataframes.items():
        # if enabled:
        strategy = strategies[name]
        df = strategy.run()
        with st.expander(f"\U0001F4C2 Detailed View: {name}"):
            if df.empty or 'pnl' not in df.columns:
                st.info("ℹ️ No trades generated for this strategy yet.")
            else:
                st.write("### Trade Log")
                st.dataframe(df, use_container_width=True)

                # df['cumulative_pnl'] = df['pnl'].cumsum()
                # st.line_chart(df.set_index("timestamp")["cumulative_pnl"])
                if 'pnl' in df.columns and not df.empty:
                    st.write("### Equity Curve")
                    df['cumulative_pnl'] = df['pnl'].cumsum()
                    st.line_chart(df.set_index("timestamp")["cumulative_pnl"])

                    st.write("### Drawdown Curve")
                    df['drawdown'] = df['cumulative_pnl'].cummax() - df['cumulative_pnl']
                    st.area_chart(df.set_index("timestamp")["drawdown"])
                else:
                    st.warning(f"No valid 'pnl' data available for {name}.")

                if 'duration' in df.columns:
                    st.write("### Trade Duration Distribution")
                    st.bar_chart(df['duration'])

                # df['drawdown'] = df['cumulative_pnl'].cummax() - df['cumulative_pnl']
                # st.area_chart(df.set_index("timestamp")["drawdown"])

                if 'duration' in df.columns:
                    st.write("### Trade Duration Distribution")
                    st.bar_chart(df['duration'])

                st.write("### Additional Metrics")
                metrics = calculate_metrics(df)
                st.json(metrics)

else:
    st.info("No strategies selected or no trades generated yet.")
