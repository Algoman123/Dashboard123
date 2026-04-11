# Dashboard123

A real-time portfolio monitoring dashboard for [Portfolio123](https://www.portfolio123.com) users. Built with Streamlit and Python.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41+-red)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

### Portfolio Monitoring
- **P123 Strategy & Screen Monitoring** — Live holdings from your Portfolio123 strategies, screens, and ranking systems
- **Ranking Radar Charts** — Spider/radar visualizations of composite ranking node scores for any ticker
- **TradingView Charts** — Full interactive TradingView charts with MA ribbon and volume overlays
- **Market Overview** — Customizable top bar with major indices, sparkline mini-charts, and daily performance
- **Top Gainers & Losers** — Real-time top movers across all your monitored tickers

### Analysis Dashboards
- **Macro Indicators** — Yield curves, GDP growth, CPI inflation, CLI leading indicators via FRED API
- **Market Sentiment** — Fear & Greed index, market breadth (advance/decline), AAII survey, Reddit mentions, and optional Adanos watchlist sentiment
- **Technicals** — Sector rotation (Relative Rotation Graph), correlation matrix, RS ranking, stage analysis
- **Factor Regimes** — Factor ETF regime analysis across value, momentum, quality, size, and volatility
- **Fundamentals Dashboard** — Earnings calendar, sector P/E valuations, dividends, analyst revisions, IPO calendar
- **Per-Ticker Fundamentals** — Detailed fundamental view for any selected stock

### Tools & Workflow
- **Strategy Trader** — Rebalance workflow panel: fetch recommendations, adjust shares, commit trades via P123 API
- **News Feed** — Per-ticker news from Yahoo Finance, plus an aggregated multi-ticker news panel
- **Community Forum** — Latest posts from the P123 community forum
- **Grok AI Analysis** — One-click deep analysis of any ticker via Grok with a customizable question template
- **Trader Notes** — Per-ticker notes that persist across sessions

### Customization
- **Dark / Light Theme** — Full theme support with a single click
- **Configurable Sidebar** — Drag-and-drop group ordering, per-group column indicators (RSI, SMA, relative volume, etc.)
- **Auto-Refresh** — Configurable refresh interval for market data

## Prerequisites

- **Python 3.10** or later
- **Portfolio123 API subscription** (for strategy/screen/ranking data and the Trader panel)
  - The dashboard works without a P123 API key, but P123-specific features will be unavailable
  - API keys are available at [https://www.portfolio123.com/sv/account-settings/dataminer-api](https://www.portfolio123.com/sv/account-settings/dataminer-api)

## Installation

### Quick Start (Windows)

1. Install [Python 3.10+](https://www.python.org/downloads/) — **check "Add Python to PATH"** during installation
2. Download or clone this repository
3. Double-click **`install.bat`** — creates a virtual environment and installs dependencies
4. Edit the **`.env`** file with your P123 API credentials
5. Double-click **`run.bat`** to launch the dashboard

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/Algoman123/Dashboard123.git
cd Dashboard123

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your P123 API credentials

# Run the dashboard
streamlit run app.py --server.port 8510
```

## Configuration

### API Credentials

Create a `.env` file (or edit the one created by `install.bat`):

```
P123_API_ID=your_api_id_here
P123_API_KEY=your_api_key_here
```

Optional API keys for the analysis dashboards (add to `.env`):

```
FRED_API_KEY=your_fred_key_here
FINNHUB_API_KEY=your_finnhub_key_here
ADANOS_API_KEY=your_adanos_key_here
```

- **FRED API key** (free) — Powers the Macro dashboard. Get one at [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
- **Finnhub API key** (free tier) — Earnings calendar and insider trades. Get one at [https://finnhub.io/register](https://finnhub.io/register)
- **Adanos API key** (optional) — Enables cross-platform market sentiment for selected watchlist tickers in the Sentiment dashboard. Get access at [https://api.adanos.org/docs/](https://api.adanos.org/docs/)
- The Sentiment, Technicals, Factor, and Fundamentals dashboards work without any API keys (they use yfinance and public data sources). Adanos sentiment is skipped unless `ADANOS_API_KEY` is configured.

### Settings Dialog

Click the **gear icon** (⚙️) in the sidebar to access settings:

- **P123 Strategies** — Add strategy IDs to monitor their holdings
- **P123 Screens** — Add screen IDs to track screen results
- **P123 Rankings** — Add ranking system IDs with universe definitions for radar charts
- **Custom Groups** — Create custom ticker watchlists (e.g., FAANG, sector ETFs)
- **Sidebar Order** — Reorder groups using ▲/▼ buttons
- **API Settings** — Enter or update your P123 API credentials
- **Data Settings** — Configure overview tickers, sparkline period, auto-refresh, movers count, Grok template
- **Trader** — Configure brokerage accounts and strategy assignments for the rebalance workflow

### First Run

On first launch, if no P123 API credentials are detected, the Settings dialog opens automatically to the API tab. The dashboard will still work without P123 credentials — you'll see market data for custom groups, indices, and sectors, but P123-specific features (strategies, screens, rankings, trader) will be unavailable.

## Updating

Your personal settings (`config.json`, `.env`, and all data files) will never be overwritten by updates.

### If you cloned with git

```bash
cd Dashboard123

# Activate virtual environment first (if using one)
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

git pull
pip install -r requirements.txt
```

### If you downloaded the ZIP

If you downloaded the ZIP from GitHub (no `.git` folder), follow these steps:

1. Download the latest ZIP from GitHub and extract it to a temporary folder
2. Copy your personal files from the old folder to the new one:
   - `.env` (your API keys)
   - `config.json` (your settings — strategies, groups, sidebar order, etc.)
   - Any `*_data.json` / `*_holdings.json` / `*_notes.json` files (your saved data)
3. Install updated dependencies in the new folder:
   ```bash
   pip install -r requirements.txt
   ```
4. Replace the old folder with the new one

**Tip:** To make future updates easier, consider switching to a git clone:
```bash
git clone https://github.com/Algoman123/Dashboard123.git
```
Then copy your `.env` and `config.json` into the cloned folder. Future updates will be a simple `git pull`.

## File Structure

```
Dashboard123/
  app.py                    Main entry point
  requirements.txt          Python dependencies
  config.example.json       Example configuration (copy to config.json)
  .env.example              API key template
  install.bat               Windows installer
  run.bat                   Windows launcher
  .streamlit/config.toml    Streamlit server settings

  components/               UI components
    sidebar.py              Sidebar with ticker groups
    chart.py                TradingView embedded chart
    market_overview.py      Market indices with sparklines
    gainers_losers.py       Top movers
    factor_dashboard.py     Factor regime analysis
    fundamentals.py         Per-ticker fundamentals
    fundamentals_dashboard.py  Earnings, valuations, dividends
    macro_dashboard.py      FRED economic indicators
    sentiment_dashboard.py  Sentiment analysis
    technicals_dashboard.py Sector rotation, correlation, stages
    forum_posts.py          P123 community feed
    news.py                 Per-ticker news
    news_feed.py            Aggregated news panel
    radar_chart.py          SVG radar charts for rankings
    settings_dialog.py      Settings UI
    trader_panel.py         Rebalance workflow

  services/                 Data & API layer
    api_keys.py             Centralized API key management
    config_manager.py       JSON config CRUD
    market_data.py          yfinance data fetching
    p123_client.py          Portfolio123 API wrapper
    factor_data.py          Factor ETF data
    fred_data.py            FRED API integration
    fundamentals_data.py    Fundamental data via yfinance
    fundamentals_dashboard_data.py  Earnings, sector valuations
    sentiment_data.py       Fear & Greed, breadth, AAII, Reddit
    technicals_data.py      Sector rotation, correlation, stages
    forum_data.py           Discourse forum API
    news_data.py            Yahoo Finance news
    trader_notes.py         Persistence for notes & data

  utils/                    Shared utilities
    constants.py            Colors, ticker names, sector ETFs
    indicators.py           Technical indicator formatting
    market_hours.py         Market open/close detection
    theme.py                Dark/light theme CSS
    p123_icon.py            SVG icons
```

## Known Limitations

- **TradingView Oslo Exchange** — The TradingView embed widget does not support Oslo Stock Exchange (OSL) stocks. The symbol search finds them, but the chart won't render. This is a TradingView embed limitation — it works fine on TradingView's own site.
- **P123 API Credits** — Ranking data fetches cost ~2 API credits per call. Holdings are cached to disk and only refreshed on manual button press.
- **yfinance Data** — Market data from Yahoo Finance may have occasional gaps or delays.

## License

MIT License — see [LICENSE](LICENSE) for details.

If you fork or redistribute this project, please keep the "Buy me a coffee" link in the sidebar and credit the original author.

## Author

**Algoman**
https://x.com/AlgoManX

---

*Built with [Streamlit](https://streamlit.io), [yfinance](https://github.com/ranaroussi/yfinance), [Portfolio123 API](https://www.portfolio123.com), and [TradingView](https://www.tradingview.com).*
