import numpy as np

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

    if 'pnl' not in df.columns or df.empty:
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
            'avg_trade_duration': 0.0
        }

    pnl = df['pnl'].dropna()
    
    # if pnl.empty:
    #     return {
    #         'sharpe': 0.0,
    #         'sortino': 0.0,
    #         'wins': 0,
    #         'losses': 0,
    #         'win_rate': 0.0,
    #         'closed_pl': 0.0,
    #         'avg_win': 0.0,
    #         'avg_loss': 0.0,
    #         'profit_factor': 0.0,
    #         'max_drawdown': 0.0,
    #         'avg_trade_duration': 0.0
    #     }

    returns = pnl
    cumulative = returns.cumsum()
    peak = cumulative.cummax()
    drawdown = peak - cumulative
    max_drawdown = drawdown.max()

    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    win_count = len(wins)
    loss_count = len(losses)

    win_rate = (win_count / len(pnl)) * 100
    avg_win = wins.mean() if win_count else 0.0
    avg_loss = losses.mean() if loss_count else 0.0
    profit_factor = abs(wins.sum() / losses.sum()) if losses.sum() != 0 else np.inf

    sharpe = pnl.mean() / (pnl.std() + 1e-9) * np.sqrt(252)
    sortino = pnl.mean() / (pnl[pnl < 0].std() + 1e-9) * np.sqrt(252)

    # Duration (optional)
    if 'duration' in df.columns:
        avg_duration = df['duration'].mean()
    else:
        avg_duration = 0.0

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
        'avg_trade_duration': avg_duration
    }
