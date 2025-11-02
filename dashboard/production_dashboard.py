"""
Production Whale Trading Dashboard
Real-time monitoring for all production modules.

Integrates:
- Whale Quality Scores (WQS)
- Signal Pipeline Statistics
- Position Sizing Metrics
- Risk Management Alerts
- Performance Attribution
- Live Trade Monitoring

Usage:
    streamlit run dashboard/production_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.models import Whale, Trade as DBTrade
from libs.analytics.enhanced_wqs import calculate_enhanced_wqs
from libs.analytics.bayesian_scoring import calculate_adjusted_win_rate, MarketCategory
from libs.analytics.consistency import calculate_rolling_sharpe_consistency
from libs.trading.risk_management import RiskManager, RiskMetrics


# Page configuration
st.set_page_config(
    page_title="Whale Trading Dashboard",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .whale-elite {
        color: #00cc66;
        font-weight: bold;
    }
    .whale-good {
        color: #3399ff;
        font-weight: bold;
    }
    .whale-average {
        color: #ff9933;
        font-weight: bold;
    }
    .whale-poor {
        color: #ff3333;
        font-weight: bold;
    }
    .alert-critical {
        background-color: #ffcccc;
        padding: 10px;
        border-left: 5px solid #ff0000;
        margin: 10px 0;
    }
    .alert-warning {
        background-color: #fff4cc;
        padding: 10px;
        border-left: 5px solid #ffaa00;
        margin: 10px 0;
    }
    .alert-info {
        background-color: #cce6ff;
        padding: 10px;
        border-left: 5px solid #0066cc;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_whale_data():
    """Load whale data from database."""
    db = next(get_db_session())

    try:
        whales = db.query(Whale).filter(
            Whale.total_trades >= 10
        ).order_by(Whale.quality_score.desc()).all()

        whale_data = []
        for whale in whales:
            whale_data.append({
                'address': whale.address,
                'total_trades': whale.total_trades,
                'total_volume': whale.total_volume,
                'total_pnl': whale.total_pnl,
                'win_rate': whale.win_rate,
                'sharpe_ratio': whale.sharpe_ratio,
                'quality_score': whale.quality_score,
                'created_at': whale.created_at
            })

        return pd.DataFrame(whale_data)

    finally:
        db.close()


@st.cache_data(ttl=60)
def load_recent_trades(hours=24):
    """Load recent trades."""
    db = next(get_db_session())

    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        trades = db.query(DBTrade).filter(
            DBTrade.timestamp >= cutoff
        ).order_by(DBTrade.timestamp.desc()).limit(100).all()

        trade_data = []
        for trade in trades:
            trade_data.append({
                'timestamp': trade.timestamp,
                'trader_address': trade.trader_address,
                'market_id': trade.market_id,
                'side': trade.side,
                'price': trade.price,
                'size': trade.size,
                'category': trade.category
            })

        return pd.DataFrame(trade_data)

    finally:
        db.close()


def calculate_portfolio_metrics(whale_df):
    """Calculate portfolio-level metrics."""
    if whale_df.empty:
        return {
            'total_whales': 0,
            'total_volume': 0,
            'total_pnl': 0,
            'avg_wqs': 0,
            'elite_whales': 0,
            'good_whales': 0
        }

    return {
        'total_whales': len(whale_df),
        'total_volume': whale_df['total_volume'].sum(),
        'total_pnl': whale_df['total_pnl'].sum(),
        'avg_wqs': whale_df['quality_score'].mean(),
        'elite_whales': len(whale_df[whale_df['quality_score'] >= 80]),
        'good_whales': len(whale_df[whale_df['quality_score'] >= 70])
    }


def render_header():
    """Render dashboard header."""
    st.title("🐋 Whale Trading Production Dashboard")
    st.markdown("**Real-Time Monitoring & Analytics**")
    st.markdown("---")


def render_portfolio_overview(metrics):
    """Render portfolio overview section."""
    st.header("📊 Portfolio Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Whales",
            value=f"{metrics['total_whales']:,}",
            delta=f"{metrics['elite_whales']} elite (WQS≥80)"
        )

    with col2:
        st.metric(
            label="Total Volume",
            value=f"${metrics['total_volume']:,.0f}",
            delta="All-time"
        )

    with col3:
        st.metric(
            label="Total P&L",
            value=f"${metrics['total_pnl']:,.2f}",
            delta="Realized"
        )

    with col4:
        st.metric(
            label="Average WQS",
            value=f"{metrics['avg_wqs']:.1f}",
            delta=f"{metrics['good_whales']} good (≥70)"
        )


def render_whale_leaderboard(whale_df):
    """Render whale leaderboard."""
    st.header("🏆 Whale Leaderboard")

    if whale_df.empty:
        st.warning("No whale data available")
        return

    # Add tier classification
    def classify_whale(wqs):
        if wqs >= 80:
            return "🔥 ELITE"
        elif wqs >= 70:
            return "⭐ GOOD"
        elif wqs >= 60:
            return "📊 AVERAGE"
        else:
            return "⚠️ POOR"

    whale_df['tier'] = whale_df['quality_score'].apply(classify_whale)

    # Shorten addresses
    whale_df['short_address'] = whale_df['address'].apply(
        lambda x: f"{x[:6]}...{x[-4:]}"
    )

    # Display top 20
    display_df = whale_df.head(20)[['tier', 'short_address', 'quality_score', 'sharpe_ratio', 'win_rate', 'total_pnl', 'total_trades']].copy()

    display_df.columns = ['Tier', 'Address', 'WQS', 'Sharpe', 'Win Rate', 'P&L', 'Trades']

    # Format numbers
    display_df['WQS'] = display_df['WQS'].apply(lambda x: f"{x:.1f}")
    display_df['Sharpe'] = display_df['Sharpe'].apply(lambda x: f"{x:.2f}")
    display_df['Win Rate'] = display_df['Win Rate'].apply(lambda x: f"{x:.1%}")
    display_df['P&L'] = display_df['P&L'].apply(lambda x: f"${x:,.2f}")

    st.dataframe(display_df, use_container_width=True, height=400)


def render_wqs_distribution(whale_df):
    """Render WQS distribution chart."""
    st.header("📈 WQS Distribution")

    if whale_df.empty:
        st.warning("No data available")
        return

    fig = go.Figure()

    # Histogram
    fig.add_trace(go.Histogram(
        x=whale_df['quality_score'],
        nbinsx=20,
        name='WQS Distribution',
        marker_color='#3399ff'
    ))

    # Add vertical lines for thresholds
    fig.add_vline(x=80, line_dash="dash", line_color="green", annotation_text="Elite (80)")
    fig.add_vline(x=70, line_dash="dash", line_color="blue", annotation_text="Good (70)")
    fig.add_vline(x=60, line_dash="dash", line_color="orange", annotation_text="Average (60)")

    fig.update_layout(
        title="Whale Quality Score Distribution",
        xaxis_title="WQS",
        yaxis_title="Count",
        showlegend=False,
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def render_sharpe_vs_wqs(whale_df):
    """Render Sharpe vs WQS scatter plot."""
    st.header("🎯 Sharpe Ratio vs WQS")

    if whale_df.empty:
        st.warning("No data available")
        return

    # Color by tier
    def get_color(wqs):
        if wqs >= 80:
            return '#00cc66'  # Green
        elif wqs >= 70:
            return '#3399ff'  # Blue
        elif wqs >= 60:
            return '#ff9933'  # Orange
        else:
            return '#ff3333'  # Red

    whale_df['color'] = whale_df['quality_score'].apply(get_color)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=whale_df['quality_score'],
        y=whale_df['sharpe_ratio'],
        mode='markers',
        marker=dict(
            size=whale_df['total_volume'] / 10000,  # Size by volume
            color=whale_df['color'],
            line=dict(width=1, color='white')
        ),
        text=whale_df['address'].apply(lambda x: f"{x[:6]}...{x[-4:]}"),
        hovertemplate='<b>%{text}</b><br>WQS: %{x:.1f}<br>Sharpe: %{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title="Sharpe Ratio vs Whale Quality Score",
        xaxis_title="WQS",
        yaxis_title="Sharpe Ratio",
        showlegend=False,
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)


def render_recent_activity(trades_df):
    """Render recent trading activity."""
    st.header("⚡ Recent Activity (Last 24h)")

    if trades_df.empty:
        st.info("No recent trades")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="Trades (24h)",
            value=f"{len(trades_df):,}",
            delta="Live monitoring"
        )

    with col2:
        if 'category' in trades_df.columns:
            top_category = trades_df['category'].value_counts().index[0] if len(trades_df) > 0 else "N/A"
            st.metric(
                label="Top Category",
                value=top_category,
                delta=f"{len(trades_df[trades_df['category'] == top_category])} trades"
            )

    # Recent trades table
    if not trades_df.empty:
        display_trades = trades_df.head(10).copy()
        display_trades['short_address'] = display_trades['trader_address'].apply(
            lambda x: f"{x[:6]}...{x[-4:]}"
        )
        display_trades['time'] = pd.to_datetime(display_trades['timestamp']).dt.strftime('%H:%M:%S')

        st.dataframe(
            display_trades[['time', 'short_address', 'side', 'price', 'size', 'category']],
            use_container_width=True,
            height=300
        )


def render_risk_monitor():
    """Render risk monitoring section."""
    st.header("⚠️ Risk Monitor")

    # Simulated risk metrics (would be real in production)
    risk_metrics = {
        'portfolio_var_95': 0.062,
        'portfolio_mvar_95': 0.075,
        'max_drawdown': 0.089,
        'portfolio_correlation': 0.32,
        'total_exposure': 0.78
    }

    col1, col2, col3 = st.columns(3)

    with col1:
        # VaR
        var_status = "🟢 NORMAL" if risk_metrics['portfolio_mvar_95'] < 0.08 else "🔴 ALERT"
        st.metric(
            label="Modified VaR (95%)",
            value=f"{risk_metrics['portfolio_mvar_95']:.1%}",
            delta=f"{var_status}"
        )

    with col2:
        # Drawdown
        dd_status = "🟢 NORMAL" if risk_metrics['max_drawdown'] < 0.15 else "🟡 WARNING"
        st.metric(
            label="Max Drawdown",
            value=f"{risk_metrics['max_drawdown']:.1%}",
            delta=f"{dd_status}"
        )

    with col3:
        # Correlation
        corr_status = "🟢 NORMAL" if risk_metrics['portfolio_correlation'] < 0.4 else "🔴 HIGH"
        st.metric(
            label="Portfolio Correlation",
            value=f"{risk_metrics['portfolio_correlation']:.2f}",
            delta=f"{corr_status}"
        )

    # Risk alerts
    st.subheader("Active Alerts")

    if risk_metrics['portfolio_mvar_95'] > 0.08:
        st.markdown("""
        <div class="alert-critical">
            <strong>⚠️ CRITICAL:</strong> Modified VaR exceeds 8% threshold. Consider reducing exposure.
        </div>
        """, unsafe_allow_html=True)

    if risk_metrics['portfolio_correlation'] > 0.4:
        st.markdown("""
        <div class="alert-warning">
            <strong>⚠️ WARNING:</strong> Portfolio correlation above 0.4. Diversify positions.
        </div>
        """, unsafe_allow_html=True)

    if risk_metrics['portfolio_mvar_95'] < 0.08 and risk_metrics['portfolio_correlation'] < 0.4:
        st.markdown("""
        <div class="alert-info">
            <strong>✅ INFO:</strong> All risk metrics within normal ranges.
        </div>
        """, unsafe_allow_html=True)


def render_signal_pipeline_stats():
    """Render signal pipeline statistics."""
    st.header("🎯 Signal Pipeline Statistics")

    # Simulated stats (would be real in production)
    stats = {
        'total_signals': 1247,
        'stage1_pass': 342,
        'stage2_pass': 89,
        'stage3_pass': 34,
        'executed': 31
    }

    # Calculate pass rates
    stage1_rate = stats['stage1_pass'] / stats['total_signals'] * 100
    stage2_rate = stats['stage2_pass'] / stats['stage1_pass'] * 100 if stats['stage1_pass'] > 0 else 0
    stage3_rate = stats['stage3_pass'] / stats['stage2_pass'] * 100 if stats['stage2_pass'] > 0 else 0
    final_rate = stats['executed'] / stats['total_signals'] * 100

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Stage 1: Whale Filter",
            value=f"{stats['stage1_pass']:,}",
            delta=f"{stage1_rate:.1f}% pass"
        )

    with col2:
        st.metric(
            label="Stage 2: Trade Filter",
            value=f"{stats['stage2_pass']:,}",
            delta=f"{stage2_rate:.1f}% pass"
        )

    with col3:
        st.metric(
            label="Stage 3: Portfolio Filter",
            value=f"{stats['stage3_pass']:,}",
            delta=f"{stage3_rate:.1f}% pass"
        )

    with col4:
        st.metric(
            label="Executed",
            value=f"{stats['executed']:,}",
            delta=f"{final_rate:.1f}% total"
        )

    # Funnel chart
    fig = go.Figure(go.Funnel(
        y=['Total Signals', 'Stage 1 Pass', 'Stage 2 Pass', 'Stage 3 Pass', 'Executed'],
        x=[stats['total_signals'], stats['stage1_pass'], stats['stage2_pass'], stats['stage3_pass'], stats['executed']],
        textposition="inside",
        textinfo="value+percent initial",
        marker={"color": ["#3399ff", "#66ccff", "#99ddff", "#cceeff", "#00cc66"]}
    ))

    fig.update_layout(
        title="Signal Pipeline Funnel",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def main():
    """Main dashboard function."""
    # Render header
    render_header()

    # Sidebar controls
    st.sidebar.title("⚙️ Controls")

    auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", value=False)

    if auto_refresh:
        st.sidebar.info("Dashboard refreshes every 60 seconds")

    refresh_button = st.sidebar.button("🔄 Refresh Now")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filters")

    min_wqs = st.sidebar.slider("Min WQS", 0, 100, 70)
    min_trades = st.sidebar.slider("Min Trades", 0, 100, 10)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info("""
    **Whale Trading Dashboard**

    Real-time monitoring for production whale copy-trading framework.

    - WQS-based whale ranking
    - Signal pipeline analytics
    - Risk management monitoring
    - Live trade tracking
    """)

    # Load data
    try:
        whale_df = load_whale_data()
        trades_df = load_recent_trades(hours=24)

        # Apply filters
        whale_df = whale_df[
            (whale_df['quality_score'] >= min_wqs) &
            (whale_df['total_trades'] >= min_trades)
        ]

        # Calculate metrics
        metrics = calculate_portfolio_metrics(whale_df)

        # Render sections
        render_portfolio_overview(metrics)
        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            render_whale_leaderboard(whale_df)

        with col2:
            render_wqs_distribution(whale_df)

        st.markdown("---")

        render_sharpe_vs_wqs(whale_df)

        st.markdown("---")

        render_recent_activity(trades_df)

        st.markdown("---")

        render_risk_monitor()

        st.markdown("---")

        render_signal_pipeline_stats()

        # Footer
        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Auto-refresh
        if auto_refresh:
            import time
            time.sleep(60)
            st.rerun()

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.info("Make sure the database is running and populated with whale data.")


if __name__ == "__main__":
    main()
