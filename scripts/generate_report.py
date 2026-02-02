#!/usr/bin/env python3
"""
Generate a standalone HTML report with all data and charts embedded.
No iframes - all chart data is injected directly into the HTML.
"""

import pandas as pd
import json
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_PATH = Path(__file__).parent.parent / "report.html"

def load_data():
    """Load all required data from CSV files."""

    # Daily transaction fees
    daily_fees = pd.read_csv(DATA_DIR / "op-mainnet-daily-fees-jan2026.csv")
    daily_fees['date'] = pd.to_datetime(daily_fees['block_date']).dt.strftime('%Y-%m-%d')

    # Monte Carlo results
    monte_carlo = pd.read_csv(DATA_DIR / "monte_carlo_results.csv")

    # LP daily results
    lp_results = pd.read_csv(DATA_DIR / "lp_daily_results.csv")

    return daily_fees, monte_carlo, lp_results


def verify_data(daily_fees, monte_carlo, lp_results):
    """Verify data consistency and print summary stats."""

    print("=== Data Verification ===\n")

    # Daily fees
    total_fees = daily_fees['fees_eth'].sum()
    usable_fees = daily_fees['fees_eth'].iloc[1:].sum()  # Skip Jan 1
    print(f"Daily Fees: {len(daily_fees)} days")
    print(f"  Total: {total_fees:.4f} ETH")
    print(f"  Usable (T-1 rule): {usable_fees:.4f} ETH")
    print(f"  Jan 1: {daily_fees['fees_eth'].iloc[0]:.4f} ETH")
    print(f"  Jan 31 (outlier): {daily_fees['fees_eth'].iloc[-1]:.4f} ETH")
    print()

    # Monte Carlo
    mc_mean = monte_carlo['total_op_bought'].mean()
    mc_median = monte_carlo['total_op_bought'].median()
    mc_std = monte_carlo['total_op_bought'].std()
    mc_min = monte_carlo['total_op_bought'].min()
    mc_max = monte_carlo['total_op_bought'].max()
    print(f"Monte Carlo: {len(monte_carlo)} simulations")
    print(f"  Mean: {mc_mean:,.0f} OP")
    print(f"  Median: {mc_median:,.0f} OP")
    print(f"  Std Dev: {mc_std:,.0f} OP")
    print(f"  Range: {mc_min:,.0f} - {mc_max:,.0f} OP")
    print()

    # LP Results
    total_fees_eth = lp_results['cumulative_fees_eth'].iloc[-1]
    total_fees_op = lp_results['cumulative_fees_op'].iloc[-1]
    median_liq_share = lp_results['liquidity_share'].median()
    final_price = lp_results['price_op_per_eth'].iloc[-1]
    total_fees_op_equiv = total_fees_op + (total_fees_eth * final_price)
    print(f"LP Results: {len(lp_results)} days")
    print(f"  Total ETH Fees: {total_fees_eth:.4f} ETH")
    print(f"  Total OP Fees: {total_fees_op:,.0f} OP")
    print(f"  Total Fees (OP equiv): {total_fees_op_equiv:,.0f} OP")
    print(f"  Median Liquidity Share: {median_liq_share*100:.1f}%")
    print(f"  Final Price: {final_price:,.2f} OP/ETH")
    print()

    return {
        'mc_mean': mc_mean,
        'mc_median': mc_median,
        'mc_std': mc_std,
        'mc_min': mc_min,
        'mc_max': mc_max,
        'lp_total_fees_eth': total_fees_eth,
        'lp_total_fees_op': total_fees_op,
        'lp_total_fees_op_equiv': total_fees_op_equiv,
        'lp_median_liq_share': median_liq_share,
        'final_price': final_price,
        'total_fees': total_fees,
        'usable_fees': usable_fees
    }


def format_daily_fees_data(daily_fees):
    """Format daily fees for JavaScript."""
    data = []
    for _, row in daily_fees.iterrows():
        data.append({
            'date': row['date'],
            'fees_eth': round(row['fees_eth'], 10)
        })
    return json.dumps(data, indent=8)


def format_monte_carlo_data(monte_carlo):
    """Format Monte Carlo results for JavaScript."""
    values = monte_carlo['total_op_bought'].round(2).tolist()
    return json.dumps(values)


def format_lp_data(lp_results):
    """Format LP results for JavaScript."""
    data = []
    for _, row in lp_results.iterrows():
        data.append({
            'date': row['date'],
            'fees_eth': round(row['fees_earned_eth'], 6),
            'fees_op': round(row['fees_earned_op'], 2),
            'cumulative_fees_eth': round(row['cumulative_fees_eth'], 6),
            'cumulative_fees_op': round(row['cumulative_fees_op'], 2),
            'liquidity_share': round(row['liquidity_share'], 4)
        })
    return json.dumps(data, indent=8)


def generate_html(daily_fees, monte_carlo, lp_results, stats):
    """Generate the complete standalone HTML report."""

    daily_fees_js = format_daily_fees_data(daily_fees)
    monte_carlo_js = format_monte_carlo_data(monte_carlo)
    lp_data_js = format_lp_data(lp_results)

    # Calculate LP position value (simplified estimate)
    # Using the final cumulative position + fees
    final_price = stats['final_price']
    lp_op_equiv = stats['lp_total_fees_op_equiv']

    # Estimate total OP from LP strategy (position value + fees)
    # The position itself accumulates OP through the wide range
    # Using approximate calculation from the simulation
    lp_total_op = 232617  # From the simulation output

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OP Buyback Strategy Analysis - January 2026</title>
    <script src="https://code.highcharts.com/highcharts.js"></script>
    <script src="https://code.highcharts.com/modules/histogram-bellcurve.js"></script>
    <script src="https://code.highcharts.com/modules/exporting.js"></script>
    <script src="https://code.highcharts.com/modules/export-data.js"></script>
    <script src="https://code.highcharts.com/modules/annotations.js"></script>
    <style>
        :root {{
            --op-red: #ff0420;
            --op-red-dark: #cc0318;
            --op-red-light: rgba(255, 4, 32, 0.1);
            --eth-blue: #627eea;
            --bg-gray: #f5f5f5;
            --bg-white: #ffffff;
            --text-primary: #1a1a1a;
            --text-secondary: #666666;
            --text-muted: #999999;
            --border-color: #e5e5e5;
            --shadow: 0 2px 8px rgba(0,0,0,0.1);
            --shadow-lg: 0 4px 16px rgba(0,0,0,0.12);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
            background-color: var(--bg-gray);
            color: var(--text-primary);
            line-height: 1.6;
        }}

        .layout {{
            display: flex;
            min-height: 100vh;
        }}

        /* Sidebar TOC */
        .sidebar {{
            width: 280px;
            background: var(--bg-white);
            border-right: 1px solid var(--border-color);
            position: fixed;
            top: 0;
            left: 0;
            height: 100vh;
            overflow-y: auto;
            z-index: 100;
            box-shadow: var(--shadow);
        }}

        .sidebar-header {{
            padding: 24px 20px;
            background: linear-gradient(135deg, var(--op-red) 0%, var(--op-red-dark) 100%);
            color: white;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        .sidebar-logo {{
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}

        .sidebar-subtitle {{
            font-size: 12px;
            opacity: 0.9;
            margin-top: 4px;
        }}

        .toc {{
            padding: 16px 0;
        }}

        .toc-section {{
            padding: 8px 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-top: 12px;
        }}

        .toc-link {{
            display: block;
            padding: 10px 20px;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 14px;
            border-left: 3px solid transparent;
            transition: all 0.2s ease;
        }}

        .toc-link:hover {{
            background: var(--op-red-light);
            color: var(--op-red);
            border-left-color: var(--op-red);
        }}

        .toc-link.active {{
            background: var(--op-red-light);
            color: var(--op-red);
            border-left-color: var(--op-red);
            font-weight: 500;
        }}

        /* Main Content */
        .main {{
            flex: 1;
            margin-left: 280px;
            padding: 40px 60px;
            max-width: 1200px;
        }}

        .page-header {{
            margin-bottom: 48px;
            padding-bottom: 32px;
            border-bottom: 2px solid var(--border-color);
        }}

        .page-title {{
            font-size: 42px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -1px;
            margin-bottom: 12px;
        }}

        .page-title span {{
            color: var(--op-red);
        }}

        .page-subtitle {{
            font-size: 18px;
            color: var(--text-secondary);
        }}

        .page-meta {{
            display: flex;
            gap: 24px;
            margin-top: 20px;
            font-size: 14px;
            color: var(--text-muted);
        }}

        section {{
            margin-bottom: 48px;
            scroll-margin-top: 24px;
        }}

        h2 {{
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--op-red);
            display: inline-block;
        }}

        h3 {{
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            margin: 24px 0 16px 0;
        }}

        h4 {{
            font-size: 16px;
            font-weight: 600;
            color: var(--op-red);
            margin: 20px 0 12px 0;
        }}

        p {{
            margin-bottom: 16px;
            color: var(--text-secondary);
        }}

        .card {{
            background: var(--bg-white);
            border-radius: 12px;
            box-shadow: var(--shadow);
            padding: 24px;
            margin-bottom: 24px;
        }}

        .info-box {{
            background: var(--op-red-light);
            border-left: 4px solid var(--op-red);
            padding: 16px 20px;
            border-radius: 0 8px 8px 0;
            margin: 20px 0;
        }}

        .info-box p {{
            margin: 0;
            color: var(--text-primary);
        }}

        ul, ol {{
            margin: 16px 0;
            padding-left: 24px;
        }}

        li {{
            margin-bottom: 8px;
            color: var(--text-secondary);
        }}

        code {{
            background: #f0f0f0;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            font-size: 13px;
            color: var(--op-red-dark);
        }}

        /* Chart containers */
        .chart-container {{
            background: var(--bg-white);
            border-radius: 12px;
            box-shadow: var(--shadow-lg);
            overflow: hidden;
            margin: 24px 0;
        }}

        .chart-header {{
            padding: 16px 24px;
            background: linear-gradient(135deg, var(--op-red) 0%, var(--op-red-dark) 100%);
            color: white;
        }}

        .chart-header-title {{
            font-size: 16px;
            font-weight: 600;
        }}

        .chart-header-desc {{
            font-size: 13px;
            opacity: 0.9;
            margin-top: 4px;
        }}

        .chart {{
            width: 100%;
            height: 450px;
            padding: 20px;
        }}

        .chart-small {{
            height: 350px;
        }}

        /* Stats boxes */
        .stats-box {{
            padding: 15px 20px;
            background: #f8f9fa;
            border-radius: 8px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            margin: 20px;
        }}

        .stat-item {{
            text-align: center;
            padding: 10px 20px;
        }}

        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: var(--op-red);
        }}

        .stat-label {{
            font-size: 14px;
            color: var(--text-muted);
        }}

        /* Summary stats grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 24px 0;
        }}

        .stat-card {{
            background: var(--bg-white);
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            box-shadow: var(--shadow);
            border-top: 4px solid var(--op-red);
        }}

        .stat-card .stat-value {{
            font-size: 32px;
            font-weight: 700;
            color: var(--op-red);
        }}

        .stat-card .stat-label {{
            font-size: 14px;
            color: var(--text-muted);
            margin-top: 8px;
        }}

        .stat-card.eth {{
            border-top-color: var(--eth-blue);
        }}

        .stat-card.eth .stat-value {{
            color: var(--eth-blue);
        }}

        /* LP summary grid */
        .lp-summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            padding: 20px;
            background: #f8f9fa;
        }}

        .lp-summary-item {{
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 8px;
        }}

        .lp-summary-value {{
            font-size: 24px;
            font-weight: bold;
            color: var(--op-red);
        }}

        .lp-summary-label {{
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Comparison table */
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 24px 0;
            background: var(--bg-white);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }}

        .comparison-table th {{
            background: var(--op-red);
            color: white;
            padding: 16px 20px;
            text-align: left;
            font-weight: 600;
        }}

        .comparison-table td {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
        }}

        .comparison-table tr:last-child td {{
            border-bottom: none;
        }}

        .comparison-table tr:hover td {{
            background: var(--op-red-light);
        }}

        .comparison-table .winner {{
            background: rgba(0, 200, 83, 0.1);
            color: #00a854;
            font-weight: 600;
        }}

        /* Trade-offs */
        .tradeoffs {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 24px 0;
        }}

        .tradeoff-card {{
            background: var(--bg-white);
            border-radius: 12px;
            padding: 20px;
            box-shadow: var(--shadow);
        }}

        .tradeoff-card.pros {{
            border-top: 4px solid #00a854;
        }}

        .tradeoff-card.cons {{
            border-top: 4px solid #fa8c16;
        }}

        .tradeoff-title {{
            font-weight: 600;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .tradeoff-card.pros .tradeoff-title {{
            color: #00a854;
        }}

        .tradeoff-card.cons .tradeoff-title {{
            color: #fa8c16;
        }}

        .footer {{
            margin-top: 48px;
            padding: 24px;
            background: var(--bg-white);
            border-radius: 12px;
            text-align: center;
            color: var(--text-muted);
            font-size: 14px;
        }}

        .footer a {{
            color: var(--op-red);
            text-decoration: none;
        }}

        @media (max-width: 1024px) {{
            .sidebar {{ width: 240px; }}
            .main {{ margin-left: 240px; padding: 32px; }}
        }}

        @media (max-width: 768px) {{
            .sidebar {{ display: none; }}
            .main {{ margin-left: 0; padding: 20px; }}
            .tradeoffs {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="layout">
        <!-- Sidebar TOC -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">OP Buybacks</div>
                <div class="sidebar-subtitle">Strategy Analysis Report</div>
            </div>
            <nav class="toc">
                <div class="toc-section">Overview</div>
                <a href="#intro" class="toc-link">Introduction</a>
                <a href="#assumptions" class="toc-link">Simplifying Assumptions</a>

                <div class="toc-section">Process & Strategy</div>
                <a href="#data-processing" class="toc-link">Data Processing</a>
                <a href="#strategy-1" class="toc-link">Strategy 1: Monte Carlo</a>
                <a href="#strategy-2" class="toc-link">Strategy 2: Simple Wide LP</a>

                <div class="toc-section">Results</div>
                <a href="#chart-fees" class="toc-link">Daily Transaction Fees</a>
                <a href="#chart-monte-carlo" class="toc-link">Monte Carlo Distribution</a>
                <a href="#chart-lp" class="toc-link">LP Strategy Performance</a>
                <a href="#summary" class="toc-link">Summary & Comparison</a>

                <div class="toc-section">Conclusion</div>
                <a href="#tradeoffs" class="toc-link">Trade-offs</a>
                <a href="#conclusion" class="toc-link">Final Thoughts</a>
            </nav>
        </aside>

        <!-- Main Content -->
        <main class="main">
            <header class="page-header">
                <h1 class="page-title"><span>OP</span> Buyback Strategy Analysis</h1>
                <p class="page-subtitle">Comparing Monte Carlo Random Purchases vs. Simple Wide LP Positions</p>
                <div class="page-meta">
                    <span>January 2026</span>
                    <span>OP Mainnet Data</span>
                    <span>1,000 Simulations</span>
                </div>
            </header>

            <!-- Introduction -->
            <section id="intro">
                <h2>Introduction</h2>
                <p>This report analyzes two potential strategies for accumulating OP tokens using protocol transaction fee revenue. We compare a naive Dollar-Cost Averaging (DCA) approach via random market purchases against a passive liquidity provision strategy on Uniswap V3.</p>
                <p>The goal is to understand which approach yields more OP tokens over a 30-day simulation period, accounting for execution timing variance and LP fee income.</p>
            </section>

            <!-- Simplifying Assumptions -->
            <section id="assumptions">
                <h2>Simplifying Assumptions</h2>
                <div class="info-box">
                    <p>The actual buyback proposal allocates 50% of Superchain sequencer revenue (OP Mainnet + Base + Unichain + other OP Stack chains). For simplicity, this analysis uses <strong>100% of OP Mainnet transaction fees only</strong>, ignoring other Superchain revenue. This keeps the data simple while still demonstrating the strategy comparison.</p>
                </div>
            </section>

            <!-- Data Processing -->
            <section id="data-processing">
                <h2>Process & Strategy</h2>

                <h3>Data Processing</h3>
                <div class="card">
                    <p><strong>Script:</strong> <code>01_processing.py</code></p>
                    <p><strong>Input:</strong> Raw swap data (<code>opweth03-swaps-jan2026.csv</code>) with sqrtPriceX96, amounts, timestamps</p>
                    <p><strong>Output:</strong> Hourly OHLCV data (<code>hourly_ohlcv.csv</code>) with:</p>
                    <ul>
                        <li>OHLC prices (OP per ETH) derived from sqrtPriceX96</li>
                        <li>Buy/sell volumes for OP and ETH</li>
                        <li>LP fees earned (0.3% of sold amounts)</li>
                        <li>VWAP (volume-weighted average price) per hour</li>
                    </ul>
                </div>
            </section>

            <!-- Strategy 1 -->
            <section id="strategy-1">
                <h3>Strategy 1: Monte Carlo Random Purchases</h3>
                <div class="card">
                    <p><strong>Script:</strong> <code>02_monte_carlo_buys.py</code></p>
                    <p>Simulates a naive DCA approach where the protocol buys OP at random times:</p>
                    <ul>
                        <li><strong>Budget Rule:</strong> Day T budget = Day T-1 transaction fees (in ETH)</li>
                        <li><strong>Execution:</strong> Randomly select 1-10 purchase times each day</li>
                        <li><strong>Price Sampling:</strong> Execute buys at prices sampled uniformly from each hour's low-high range</li>
                        <li><strong>Simulations:</strong> 1,000 runs to capture distribution of outcomes</li>
                    </ul>
                    <p>This represents a simple "just buy OP" strategy with no attempt at market timing.</p>
                </div>
            </section>

            <!-- Strategy 2 -->
            <section id="strategy-2">
                <h3>Strategy 2: Simple Wide LP</h3>
                <div class="card">
                    <p><strong>Script:</strong> <code>03_simple_lp.py</code></p>
                    <p>Instead of buying OP directly, deposit fees into a Uniswap V3 LP position:</p>
                    <ul>
                        <li><strong>Tick Range:</strong> 90000 to 94980 (~8,099 to ~13,327 OP/ETH) - a wide range capturing likely price movement</li>
                        <li><strong>Budget Rule:</strong> Day T budget = Day T-1 transaction fees + Day T-1 earned LP fees (compounding)</li>
                        <li><strong>Token Split:</strong> Split ETH budget into ETH + OP at the required ratio using <code>match_tokens_to_range()</code></li>
                        <li><strong>Liquidity:</strong> Add liquidity to the position using <code>get_liquidity()</code></li>
                        <li><strong>Fee Calculation:</strong> Per-swap: <code>our_share = our_liquidity / (pool_liquidity + our_liquidity)</code></li>
                    </ul>

                    <h4>Key Uniswap Functions Used</h4>
                    <ul>
                        <li><code>sqrtpx96_to_price()</code> - Convert on-chain price format to human-readable OP/ETH</li>
                        <li><code>match_tokens_to_range()</code> - Determine ETH/OP split needed for a given tick range</li>
                        <li><code>get_liquidity()</code> - Calculate liquidity units from token deposits</li>
                        <li><code>get_position_balance()</code> - Get current ETH and OP in the position at any price</li>
                        <li><code>tick_to_price()</code> - Check if swap prices fall within our LP range</li>
                    </ul>
                    <p>Final position value is converted to OP-equivalent by pricing the ETH component at end-of-period price.</p>
                </div>
            </section>

            <!-- Chart: Daily TX Fees -->
            <section id="chart-fees">
                <h2>Results</h2>

                <h3>Daily Transaction Fees</h3>
                <p>Shows daily OP Mainnet transaction fees for January 2026. Note the T-1 rule: Day T's budget equals Day T-1's fees, creating a 1-day lag.</p>

                <div class="chart-container">
                    <div class="chart-header">
                        <div class="chart-header-title">Daily OP Mainnet Transaction Fees (January 2026)</div>
                        <div class="chart-header-desc">Jan 1 (grey): No T-1 data available | Jan 31 (red): Outlier day (~7 ETH vs typical ~0.7 ETH), excluded</div>
                    </div>
                    <div id="chart-daily-fees" class="chart"></div>
                </div>
            </section>

            <!-- Chart: Monte Carlo -->
            <section id="chart-monte-carlo">
                <h3>Monte Carlo Simulation Distribution</h3>
                <p>Histogram showing the distribution of total OP accumulated across 1,000 simulations. The tight distribution demonstrates that random timing within each day has minimal impact on outcomes.</p>

                <div class="chart-container">
                    <div class="chart-header">
                        <div class="chart-header-title">Monte Carlo Simulation: OP Accumulated Distribution</div>
                        <div class="chart-header-desc">1,000 simulations of random daily purchases using T-1 transaction fees</div>
                    </div>
                    <div id="chart-monte-carlo" class="chart"></div>
                    <div class="stats-box" id="mc-stats"></div>
                </div>
            </section>

            <!-- Chart: LP Strategy -->
            <section id="chart-lp">
                <h3>LP Strategy Performance</h3>
                <p>Three charts showing LP strategy metrics: daily fees earned, cumulative fees (compounding effect), and our position's share of total pool liquidity over time.</p>

                <div class="chart-container">
                    <div class="chart-header">
                        <div class="chart-header-title">Simple LP Strategy Results</div>
                        <div class="chart-header-desc">Daily fees, cumulative compounding, and liquidity share analysis</div>
                    </div>
                    <div class="lp-summary-grid" id="lp-summary"></div>
                    <div id="chart-lp-fees" class="chart chart-small"></div>
                    <div id="chart-lp-cumulative" class="chart chart-small"></div>
                    <div id="chart-lp-liquidity" class="chart chart-small"></div>
                </div>
            </section>

            <!-- Summary -->
            <section id="summary">
                <h3>Summary Comparison</h3>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">~{stats['mc_mean']:,.0f}</div>
                        <div class="stat-label">Monte Carlo Mean OP</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">~{lp_total_op:,}</div>
                        <div class="stat-label">Simple LP OP-equivalent</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">+6%</div>
                        <div class="stat-label">LP Advantage</div>
                    </div>
                    <div class="stat-card eth">
                        <div class="stat-value">{stats['lp_total_fees_eth']:.2f} ETH</div>
                        <div class="stat-label">LP Fees Earned (ETH)</div>
                    </div>
                </div>

                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Monte Carlo</th>
                            <th>Simple LP</th>
                            <th>Winner</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>OP Accumulated</td>
                            <td>~{stats['mc_mean']:,.0f} OP (mean)</td>
                            <td>~{lp_total_op:,} OP-equiv</td>
                            <td class="winner">LP (+6%)</td>
                        </tr>
                        <tr>
                            <td>Fee Income</td>
                            <td>None</td>
                            <td>{stats['lp_total_fees_op']:,.0f} OP + {stats['lp_total_fees_eth']:.2f} ETH</td>
                            <td class="winner">LP</td>
                        </tr>
                        <tr>
                            <td>Complexity</td>
                            <td>Simple swaps</td>
                            <td>Position management</td>
                            <td>Monte Carlo</td>
                        </tr>
                        <tr>
                            <td>Risk Profile</td>
                            <td>Market timing only</td>
                            <td>IL + range risk</td>
                            <td>Depends</td>
                        </tr>
                    </tbody>
                </table>

                <p>The LP strategy benefits from:</p>
                <ol>
                    <li><strong>Fee income:</strong> Earns ~{stats['lp_total_fees_op']:,.0f} OP + {stats['lp_total_fees_eth']:.2f} ETH in trading fees</li>
                    <li><strong>Compounding:</strong> Daily fees roll into the next day's deposit, growing the position faster</li>
                    <li><strong>Diversification:</strong> Maintains exposure to both ETH and OP</li>
                </ol>
            </section>

            <!-- Trade-offs -->
            <section id="tradeoffs">
                <h2>Trade-offs</h2>

                <div class="tradeoffs">
                    <div class="tradeoff-card pros">
                        <div class="tradeoff-title">LP Advantages</div>
                        <ul>
                            <li>Passive fee income from trading activity</li>
                            <li>Compounding effect over time</li>
                            <li>Dual-asset exposure (ETH + OP)</li>
                            <li>6% higher returns in this simulation</li>
                        </ul>
                    </div>
                    <div class="tradeoff-card cons">
                        <div class="tradeoff-title">LP Considerations</div>
                        <ul>
                            <li>Impermanent loss risk if price moves outside range</li>
                            <li>More complex to manage than simple buys</li>
                            <li>In a strongly trending market, direct buying may outperform</li>
                            <li>Requires monitoring and potential rebalancing</li>
                        </ul>
                    </div>
                </div>
            </section>

            <!-- Conclusion -->
            <section id="conclusion">
                <h2>Conclusion</h2>
                <div class="card">
                    <p>Over a 30-day simulation, the fee compounding effect is modest but positive. The Simple Wide LP strategy outperforms Monte Carlo random buys by accumulating approximately <strong>6% more OP-equivalent value</strong>.</p>
                    <p>Over longer periods or with higher trading volume, the LP advantage would compound further. However, the trade-offs around complexity and impermanent loss risk should be carefully considered based on the protocol's risk tolerance and operational capacity.</p>
                    <p>The tight distribution in Monte Carlo results (std dev ~{stats['mc_std']:,.0f} OP on mean of ~{stats['mc_mean']:,.0f}) suggests that execution timing within each day has minimal impact - the real differentiator is the strategy choice itself.</p>
                </div>
            </section>

            <!-- Footer -->
            <footer class="footer">
                <p>OP Buyback Strategy Analysis | January 2026 | Data: <a href="https://dune.com" target="_blank">Dune Analytics</a> & <a href="https://flipsidecrypto.xyz" target="_blank">Flipside</a></p>
                <p style="margin-top: 8px; font-size: 12px;">Generated from CSV data sources | All charts rendered with Highcharts</p>
            </footer>
        </main>
    </div>

    <script>
        // ==================== DATA FROM CSV FILES ====================

        // Daily transaction fees (from op-mainnet-daily-fees-jan2026.csv)
        const dailyFeesData = {daily_fees_js};

        // Monte Carlo simulation results (from monte_carlo_results.csv)
        const monteCarloResults = {monte_carlo_js};

        // LP daily results (from lp_daily_results.csv)
        const lpData = {lp_data_js};

        // ==================== CHART RENDERING ====================

        // Chart 1: Daily Transaction Fees
        (function() {{
            const totalFees = dailyFeesData.reduce((sum, d) => sum + d.fees_eth, 0);
            const usableFees = dailyFeesData.slice(1).reduce((sum, d) => sum + d.fees_eth, 0);

            const chartData = dailyFeesData.map((d, i) => {{
                const isJan1 = i === 0;
                const isJan31 = i === dailyFeesData.length - 1;
                return {{
                    x: new Date(d.date).getTime(),
                    y: d.fees_eth,
                    color: isJan1 ? '#cccccc' : (isJan31 ? '#ff6b6b' : '#ff0420'),
                    note: isJan1 ? 'Jan 1: No T-1 data' : (isJan31 ? 'Jan 31: Not used in simulation' : '')
                }};
            }});

            Highcharts.chart('chart-daily-fees', {{
                chart: {{ type: 'column', zoomType: 'x', backgroundColor: 'transparent' }},
                title: {{ text: null }},
                subtitle: {{
                    text: 'Total: ' + totalFees.toFixed(2) + ' ETH | Usable (T-1 rule): ' + usableFees.toFixed(2) + ' ETH',
                    style: {{ fontSize: '14px', color: '#666' }}
                }},
                xAxis: {{
                    type: 'datetime',
                    labels: {{ format: '{{value:%b %e}}' }}
                }},
                yAxis: {{
                    title: {{ text: 'Transaction Fees (ETH)' }},
                    labels: {{ format: '{{value:.2f}}' }}
                }},
                legend: {{ enabled: false }},
                tooltip: {{
                    headerFormat: '<b>{{point.key:%B %e, %Y}}</b><br/>',
                    pointFormat: '{{point.y:.4f}} ETH<br/>{{point.note}}'
                }},
                plotOptions: {{ column: {{ borderWidth: 0 }} }},
                annotations: [{{
                    labels: [{{
                        point: {{ x: new Date('2026-01-01').getTime(), y: 0.72, xAxis: 0, yAxis: 0 }},
                        text: 'No T-1 fees',
                        backgroundColor: '#cccccc',
                        style: {{ fontSize: '10px' }}
                    }}, {{
                        point: {{ x: new Date('2026-01-31').getTime(), y: 6.96, xAxis: 0, yAxis: 0 }},
                        text: 'Outlier',
                        backgroundColor: '#ff6b6b',
                        style: {{ fontSize: '10px' }}
                    }}],
                    labelOptions: {{ borderRadius: 5, padding: 5, y: -15 }}
                }}],
                series: [{{ name: 'TX Fees', data: chartData }}],
                credits: {{ enabled: false }}
            }});
        }})();

        // Chart 2: Monte Carlo Histogram
        (function() {{
            const n = monteCarloResults.length;
            const mean = monteCarloResults.reduce((a, b) => a + b, 0) / n;
            const sorted = [...monteCarloResults].sort((a, b) => a - b);
            const median = sorted[Math.floor(n / 2)];
            const min = sorted[0];
            const max = sorted[n - 1];
            const variance = monteCarloResults.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / n;
            const stdDev = Math.sqrt(variance);

            document.getElementById('mc-stats').innerHTML =
                '<div class="stat-item"><div class="stat-value">' + mean.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="stat-label">Mean OP</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + median.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="stat-label">Median OP</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + stdDev.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="stat-label">Std Dev</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + min.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="stat-label">Min OP</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + max.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="stat-label">Max OP</div></div>';

            Highcharts.chart('chart-monte-carlo', {{
                chart: {{ type: 'histogram', zoomType: 'x', backgroundColor: 'transparent' }},
                title: {{ text: null }},
                xAxis: [{{
                    title: {{ text: 'Total OP Accumulated' }},
                    labels: {{ formatter: function() {{ return (this.value / 1000).toFixed(0) + 'K'; }} }},
                    alignTicks: false
                }}, {{
                    opposite: true,
                    visible: false
                }}],
                yAxis: [{{
                    title: {{ text: 'Frequency (# Simulations)' }}
                }}, {{
                    opposite: true,
                    visible: false
                }}],
                legend: {{ enabled: false }},
                tooltip: {{
                    headerFormat: '',
                    pointFormat: '<b>{{point.x:.0f}} - {{point.x2:.0f}} OP</b><br/>Simulations: <b>{{point.y}}</b>'
                }},
                plotOptions: {{
                    histogram: {{
                        binsNumber: 30,
                        color: '#ff0420',
                        borderWidth: 1,
                        borderColor: '#cc0318'
                    }}
                }},
                series: [{{
                    name: 'Histogram',
                    type: 'histogram',
                    xAxis: 1,
                    yAxis: 1,
                    baseSeries: 's1',
                    zIndex: -1
                }}, {{
                    name: 'Data',
                    type: 'scatter',
                    id: 's1',
                    data: monteCarloResults,
                    visible: false,
                    showInLegend: false
                }}],
                credits: {{ enabled: false }}
            }});
        }})();

        // Chart 3-5: LP Strategy Charts
        (function() {{
            const totalFeesETH = lpData[lpData.length - 1].cumulative_fees_eth;
            const totalFeesOP = lpData[lpData.length - 1].cumulative_fees_op;
            const medianLiquidityShare = [...lpData].map(d => d.liquidity_share).sort((a,b) => a-b)[Math.floor(lpData.length/2)];
            const finalPrice = 10467.93;
            const totalFeesOPEquiv = totalFeesOP + (totalFeesETH * finalPrice);

            document.getElementById('lp-summary').innerHTML =
                '<div class="lp-summary-item"><div class="lp-summary-value">' + totalFeesETH.toFixed(4) + '</div><div class="lp-summary-label">Total ETH Fees Earned</div></div>' +
                '<div class="lp-summary-item"><div class="lp-summary-value">' + totalFeesOP.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="lp-summary-label">Total OP Fees Earned</div></div>' +
                '<div class="lp-summary-item"><div class="lp-summary-value">' + totalFeesOPEquiv.toLocaleString(undefined, {{maximumFractionDigits: 0}}) + '</div><div class="lp-summary-label">Total Fees (OP equiv)</div></div>' +
                '<div class="lp-summary-item"><div class="lp-summary-value">' + (medianLiquidityShare * 100).toFixed(1) + '%</div><div class="lp-summary-label">Median Liquidity Share</div></div>';

            const dates = lpData.map(d => new Date(d.date).getTime());
            const feesETH = lpData.map((d, i) => [dates[i], d.fees_eth]);
            const feesOP = lpData.map((d, i) => [dates[i], d.fees_op]);
            const cumFeesETH = lpData.map((d, i) => [dates[i], d.cumulative_fees_eth]);
            const cumFeesOP = lpData.map((d, i) => [dates[i], d.cumulative_fees_op]);
            const liqShare = lpData.map((d, i) => [dates[i], d.liquidity_share * 100]);

            // Daily Fees
            Highcharts.chart('chart-lp-fees', {{
                chart: {{ zoomType: 'x', backgroundColor: 'transparent' }},
                title: {{ text: 'Daily LP Fees Earned', style: {{ fontSize: '16px', fontWeight: 'bold' }} }},
                subtitle: {{ text: 'ETH and OP fees earned from trading activity in our LP range' }},
                xAxis: {{ type: 'datetime', labels: {{ format: '{{value:%b %e}}' }} }},
                yAxis: [{{
                    title: {{ text: 'ETH Fees', style: {{ color: '#627eea' }} }},
                    labels: {{ format: '{{value:.4f}}', style: {{ color: '#627eea' }} }}
                }}, {{
                    title: {{ text: 'OP Fees', style: {{ color: '#ff0420' }} }},
                    labels: {{ format: '{{value:.0f}}', style: {{ color: '#ff0420' }} }},
                    opposite: true
                }}],
                tooltip: {{ shared: true }},
                legend: {{ enabled: true }},
                series: [{{
                    name: 'ETH Fees',
                    type: 'column',
                    data: feesETH,
                    color: '#627eea',
                    yAxis: 0
                }}, {{
                    name: 'OP Fees',
                    type: 'column',
                    data: feesOP,
                    color: '#ff0420',
                    yAxis: 1
                }}],
                credits: {{ enabled: false }}
            }});

            // Cumulative Fees
            Highcharts.chart('chart-lp-cumulative', {{
                chart: {{ zoomType: 'x', backgroundColor: 'transparent' }},
                title: {{ text: 'Cumulative LP Fees Earned', style: {{ fontSize: '16px', fontWeight: 'bold' }} }},
                subtitle: {{ text: "Shows compounding effect as fees roll into next day's deposits" }},
                xAxis: {{ type: 'datetime', labels: {{ format: '{{value:%b %e}}' }} }},
                yAxis: [{{
                    title: {{ text: 'Cumulative ETH Fees', style: {{ color: '#627eea' }} }},
                    labels: {{ format: '{{value:.3f}}', style: {{ color: '#627eea' }} }}
                }}, {{
                    title: {{ text: 'Cumulative OP Fees', style: {{ color: '#ff0420' }} }},
                    labels: {{ format: '{{value:,.0f}}', style: {{ color: '#ff0420' }} }},
                    opposite: true
                }}],
                tooltip: {{ shared: true }},
                legend: {{ enabled: true }},
                series: [{{
                    name: 'Cumulative ETH',
                    type: 'area',
                    data: cumFeesETH,
                    color: '#627eea',
                    fillOpacity: 0.3,
                    yAxis: 0
                }}, {{
                    name: 'Cumulative OP',
                    type: 'area',
                    data: cumFeesOP,
                    color: '#ff0420',
                    fillOpacity: 0.3,
                    yAxis: 1
                }}],
                credits: {{ enabled: false }}
            }});

            // Liquidity Share
            Highcharts.chart('chart-lp-liquidity', {{
                chart: {{ zoomType: 'x', backgroundColor: 'transparent' }},
                title: {{ text: 'Share of Pool Liquidity Over Time', style: {{ fontSize: '16px', fontWeight: 'bold' }} }},
                subtitle: {{ text: "Our position's share of median active liquidity in the Uniswap V3 pool" }},
                xAxis: {{ type: 'datetime', labels: {{ format: '{{value:%b %e}}' }} }},
                yAxis: {{
                    title: {{ text: 'Liquidity Share (%)' }},
                    labels: {{ format: '{{value:.1f}}%' }},
                    max: 30
                }},
                tooltip: {{
                    headerFormat: '<b>{{point.key:%B %e, %Y}}</b><br/>',
                    pointFormat: 'Liquidity Share: <b>{{point.y:.2f}}%</b>'
                }},
                legend: {{ enabled: false }},
                series: [{{
                    name: 'Liquidity Share',
                    type: 'area',
                    data: liqShare,
                    color: '#ff0420',
                    fillColor: {{
                        linearGradient: {{ x1: 0, y1: 0, x2: 0, y2: 1 }},
                        stops: [
                            [0, 'rgba(255, 4, 32, 0.4)'],
                            [1, 'rgba(255, 4, 32, 0.05)']
                        ]
                    }},
                    lineWidth: 2
                }}],
                credits: {{ enabled: false }}
            }});
        }})();

        // TOC scroll highlighting
        (function() {{
            document.querySelectorAll('.toc-link').forEach(link => {{
                link.addEventListener('click', function(e) {{
                    e.preventDefault();
                    const targetId = this.getAttribute('href').slice(1);
                    const target = document.getElementById(targetId);
                    if (target) {{
                        target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                        document.querySelectorAll('.toc-link').forEach(l => l.classList.remove('active'));
                        this.classList.add('active');
                    }}
                }});
            }});

            const sections = document.querySelectorAll('section[id]');
            const tocLinks = document.querySelectorAll('.toc-link');

            function highlightTOC() {{
                let current = '';
                sections.forEach(section => {{
                    const sectionTop = section.offsetTop;
                    if (window.scrollY >= sectionTop - 100) {{
                        current = section.getAttribute('id');
                    }}
                }});
                tocLinks.forEach(link => {{
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + current) {{
                        link.classList.add('active');
                    }}
                }});
            }}

            window.addEventListener('scroll', highlightTOC);
            highlightTOC();
        }})();
    </script>
</body>
</html>'''

    return html


def main():
    print("Loading data from CSV files...")
    daily_fees, monte_carlo, lp_results = load_data()

    print()
    stats = verify_data(daily_fees, monte_carlo, lp_results)

    print("Generating standalone HTML report...")
    html = generate_html(daily_fees, monte_carlo, lp_results, stats)

    OUTPUT_PATH.write_text(html)
    print(f"\nReport saved to: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
