import numpy as np
import pandas as pd

def calculate_metrics(df):
    """
    Calculates comprehensive performance metrics for a trading strategy.

    Expected columns in df:
        - 'pnl': float, profit or loss per trade
        - 'timestamp': datetime, when the trade closed

    Optional columns (if present):
        - 'duration': time in seconds
        - 'position_size': trade volume
        - 'entry_price', 'exit_price'

    Returns:
        dict: A dictionary with multiple performance metrics
    """

    # Ensure pnl exists and is numeric
    if 'pnl' not in df.columns or df.empty:
        return default_metrics()

    df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')
    pnl = df['pnl'].dropna()

    if len(pnl) < 2:
        return {
            'sharpe': 0,
            'sortino': 0,
            'win_rate': 0,
            'wins': int((pnl > 0).sum()),
            'losses': int((pnl < 0).sum()),
            'closed_pl': pnl.sum(),
            'avg_win': pnl[pnl > 0].mean() if any(pnl > 0) else 0,
            'avg_loss': pnl[pnl < 0].mean() if any(pnl < 0) else 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'avg_trade_duration': df['duration'].dropna().mean() if 'duration' in df.columns else 0,
        }

    # Debug print (optional)
    # print("📊 Metrics Debug:\n", df.head(), "\nPNL dtype:", df["pnl"].dtype)

    if pnl.empty or len(pnl) < 2 or pnl.sum() == 0:
        return default_metrics(n=len(pnl))

    returns = pnl
    cumulative = returns.cumsum()
    peak = cumulative.cummax()
    drawdown = peak - cumulative
    max_drawdown = drawdown.max()

    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    win_count = len(wins)
    loss_count = len(losses)

    avg_win = wins.mean() if win_count else 0.0
    avg_loss = losses.mean() if loss_count else 0.0

    win_rate = (win_count / len(pnl)) * 100 if len(pnl) > 0 else 0.0
    profit_factor = abs(wins.sum() / losses.sum()) if losses.sum() != 0 else np.inf

    sharpe = 0.0
    sortino = 0.0
    if pnl.std() > 0:
        sharpe = pnl.mean() / (pnl.std() + 1e-9) * np.sqrt(252)
    if pnl[pnl < 0].std() > 0:
        sortino = pnl.mean() / (pnl[pnl < 0].std() + 1e-9) * np.sqrt(252)

    # Duration
    avg_duration = 0.0
    if 'duration' in df.columns and not df['duration'].dropna().empty:
        avg_duration = round(df['duration'].dropna().mean(), 2)

    return {
        'sharpe': sharpe,
        'sortino': sortino,
        'wins': win_count,
        'losses': loss_count,
        'win_rate': win_rate,
        'closed_pl': pnl.sum(),
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'avg_trade_duration': avg_duration,
        'total_pnl': pnl.sum(),
        'number_of_trades': len(pnl)
    }

def default_metrics(n=0):
    return {
        'sharpe': 0.0,
        'sortino': 0.0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0.0,
        'closed_pl': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'profit_factor': 0.0,
        'max_drawdown': 0.0,
        'avg_trade_duration': 0.0,
        'total_pnl': 0.0,
        'number_of_trades': 0
    }
