import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

_DEFAULT_INDICES = ["SPY", "QQQ", "DIA", "IWM"]
_DEFAULT_SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "XLC"]
_DEFAULT_CANSLIM = ["XLF", "QQQ", "SMH", "GBTC", "XLK", "KRE", "IWM"]

_DEFAULT_GROK_TEMPLATE = (
    "Analyze {ticker} as a potential stock purchase. Cover the following:\n\n"
    "1) Recent News & Events — Summarize the most significant news from the "
    "past 30 days. Flag any material events (lawsuits, FDA decisions, M&A, "
    "management changes, product launches/failures).\n\n"
    "2) Latest Earnings — Review the most recent quarterly report. How did "
    "revenue, EPS, and guidance compare to analyst expectations? Any notable "
    "margin trends or one-time items?\n\n"
    "3) Financial Health — Assess debt-to-equity, cash position, free cash "
    "flow trend, and current ratio. Is the company at risk of dilution or "
    "liquidity issues?\n\n"
    "4) Risk Factors — Identify the top risks: regulatory, competitive, "
    "macro/sector headwinds, customer concentration, currency exposure, or "
    "pending litigation.\n\n"
    "5) Insider & Institutional Activity — Any notable insider selling or "
    "buying in the past 90 days? Major institutional ownership changes?\n\n"
    "6) Analyst Sentiment — What is the current consensus rating and price "
    "target? Any recent upgrades or downgrades?\n\n"
    "Conclude with a clear bullet list of the top 3-5 risks I should be "
    "aware of before buying, and rate the overall risk level as "
    "Low / Medium / High."
)

DEFAULT_CONFIG = {
    "strategies": [
        {"name": "Built for Stability", "strategy_id": 1457941, "col2": "1M", "col3": "3M"},
        {"name": "Small Cap Focus", "strategy_id": 1701030, "col2": "1M", "col3": "3M"},
    ],
    "screens": [
        {"name": "Buffet", "screen_id": 30540, "max_holdings": 25, "col2": "1M", "col3": "3M"},
    ],
    "rankings": [
        {"name": "Core Combination", "ranking_id": 408565, "universe": "Easy to Trade US",
         "max_holdings": 25, "col2": "1M", "col3": "3M", "news_feed": True},
        {"name": "Classic Quality", "ranking_id": 295373, "universe": "Easy to Trade US",
         "max_holdings": 25, "col2": "1M", "col3": "3M", "news_feed": True},
    ],
    "custom_groups": [
        {"name": "Indices", "tickers": _DEFAULT_INDICES, "col2": "1M", "col3": "3M", "news_feed": False},
        {"name": "Sectors", "tickers": _DEFAULT_SECTORS, "col2": "1M", "col3": "3M", "news_feed": False},
        {"name": "CANSLIM Timing", "tickers": _DEFAULT_CANSLIM, "col2": "1M", "col3": "SMA20", "news_feed": False},
    ],
    "sidebar_order": [
        {"type": "custom", "name": "Indices"},
        {"type": "custom", "name": "Sectors"},
        {"type": "custom", "name": "CANSLIM Timing"},
        {"type": "screen", "name": "Buffet"},
        {"type": "strategy", "name": "Built for Stability"},
        {"type": "strategy", "name": "Small Cap Focus"},
        {"type": "ranking", "name": "Core Combination"},
        {"type": "ranking", "name": "Classic Quality"},
    ],
    "settings": {
        "default_ticker": "SPY",
        "theme": "dark",
        "refresh_interval_minutes": 15,
        "sparkline_period": "5d",
        "sidebar_second_col": "5D",
        "overview_tickers": ["^GSPC", "^NDX", "^RUT", "^N100", "^N225", "^VIX", "GC=F"],
        "grok_question_template": _DEFAULT_GROK_TEMPLATE,
    },
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    config = _migrate(config)
    return config


def _migrate(config: dict) -> dict:
    """Migrate old configs: seed Indices/Sectors as custom groups & build sidebar_order."""
    changed = False

    # Ensure screens list exists
    if "screens" not in config:
        config["screens"] = []
        changed = True

    # Ensure rankings list exists
    if "rankings" not in config:
        config["rankings"] = []
        changed = True

    groups = config.get("custom_groups", [])
    group_names = {g["name"] for g in groups}

    # Seed Indices if not present
    if "Indices" not in group_names:
        groups.insert(0, {"name": "Indices", "tickers": _DEFAULT_INDICES})
        changed = True
    # Seed Sectors if not present
    if "Sectors" not in group_names:
        idx = next((i for i, g in enumerate(groups) if g["name"] == "Indices"), len(groups))
        groups.insert(idx + 1, {"name": "Sectors", "tickers": _DEFAULT_SECTORS})
        changed = True

    config["custom_groups"] = groups

    # Build sidebar_order if missing
    if "sidebar_order" not in config:
        order = []
        for g in groups:
            order.append({"type": "custom", "name": g["name"]})
        for s in config.get("strategies", []):
            order.append({"type": "strategy", "name": s["name"]})
        for s in config.get("screens", []):
            order.append({"type": "screen", "name": s["name"]})
        for r in config.get("rankings", []):
            order.append({"type": "ranking", "name": r["name"]})
        config["sidebar_order"] = order
        changed = True

    # Migrate per-group column settings (col2/col3)
    global_second = config.get("settings", {}).get("sidebar_second_col", "1M")
    all_groups = (
        config.get("custom_groups", [])
        + config.get("strategies", [])
        + config.get("screens", [])
        + config.get("rankings", [])
    )
    for group in all_groups:
        if "col2" not in group:
            group["col2"] = global_second
            changed = True
        if "col3" not in group:
            group["col3"] = "3M"
            changed = True

    # Ensure trader_accounts list exists
    if "trader_accounts" not in config:
        config["trader_accounts"] = []
        changed = True

    # Seed Grok question template if missing
    if "grok_question_template" not in config.get("settings", {}):
        config.setdefault("settings", {})["grok_question_template"] = _DEFAULT_GROK_TEMPLATE
        changed = True

    if changed:
        save_config(config)
    return config


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _append_to_order(config: dict, entry_type: str, name: str):
    """Append a new entry to sidebar_order if not already present."""
    order = config.setdefault("sidebar_order", [])
    if not any(e["type"] == entry_type and e["name"] == name for e in order):
        order.append({"type": entry_type, "name": name})


def _remove_from_order(config: dict, entry_type: str, name: str):
    """Remove an entry from sidebar_order."""
    config["sidebar_order"] = [
        e for e in config.get("sidebar_order", [])
        if not (e["type"] == entry_type and e["name"] == name)
    ]


# ---- Strategies ----

def add_strategy(config: dict, name: str, strategy_id: int) -> dict:
    strategies = config.get("strategies", [])
    if any(s["strategy_id"] == strategy_id for s in strategies):
        return config
    strategies.append({"name": name, "strategy_id": strategy_id, "col2": "1M", "col3": "3M"})
    config["strategies"] = strategies
    _append_to_order(config, "strategy", name)
    return config


def remove_strategy(config: dict, strategy_id: int) -> dict:
    for s in config.get("strategies", []):
        if s["strategy_id"] == strategy_id:
            _remove_from_order(config, "strategy", s["name"])
            break
    config["strategies"] = [
        s for s in config.get("strategies", []) if s["strategy_id"] != strategy_id
    ]
    return config


def move_strategy(config: dict, index: int, direction: int) -> dict:
    strategies = config.get("strategies", [])
    new_index = index + direction
    if 0 <= new_index < len(strategies):
        strategies[index], strategies[new_index] = strategies[new_index], strategies[index]
    config["strategies"] = strategies
    return config


# ---- Screens ----

def add_screen(config: dict, name: str, screen_id: int, max_holdings: int = 50) -> dict:
    screens = config.get("screens", [])
    if any(s["screen_id"] == screen_id for s in screens):
        return config
    screens.append({"name": name, "screen_id": screen_id, "max_holdings": max_holdings, "col2": "1M", "col3": "3M"})
    config["screens"] = screens
    _append_to_order(config, "screen", name)
    return config


def remove_screen(config: dict, screen_id: int) -> dict:
    for s in config.get("screens", []):
        if s["screen_id"] == screen_id:
            _remove_from_order(config, "screen", s["name"])
            break
    config["screens"] = [
        s for s in config.get("screens", []) if s["screen_id"] != screen_id
    ]
    return config


def move_screen(config: dict, index: int, direction: int) -> dict:
    screens = config.get("screens", [])
    new_index = index + direction
    if 0 <= new_index < len(screens):
        screens[index], screens[new_index] = screens[new_index], screens[index]
    config["screens"] = screens
    return config


# ---- Custom Groups ----

def add_custom_group(config: dict, name: str, tickers: list[str]) -> dict:
    groups = config.get("custom_groups", [])
    if any(g["name"] == name for g in groups):
        return config
    groups.append({"name": name, "tickers": tickers, "col2": "1M", "col3": "3M"})
    config["custom_groups"] = groups
    _append_to_order(config, "custom", name)
    return config


def remove_custom_group(config: dict, name: str) -> dict:
    config["custom_groups"] = [
        g for g in config.get("custom_groups", []) if g["name"] != name
    ]
    _remove_from_order(config, "custom", name)
    return config


def update_custom_group_tickers(config: dict, name: str, tickers: list[str]) -> dict:
    for g in config.get("custom_groups", []):
        if g["name"] == name:
            g["tickers"] = tickers
            break
    return config


def move_custom_group(config: dict, index: int, direction: int) -> dict:
    groups = config.get("custom_groups", [])
    new_index = index + direction
    if 0 <= new_index < len(groups):
        groups[index], groups[new_index] = groups[new_index], groups[index]
    config["custom_groups"] = groups
    return config


# ---- Rankings ----


def add_ranking(config: dict, name: str, ranking_id: int,
                universe: str, max_holdings: int = 25) -> dict:
    rankings = config.get("rankings", [])
    if any(r["ranking_id"] == ranking_id for r in rankings):
        return config
    rankings.append({
        "name": name, "ranking_id": ranking_id,
        "universe": universe, "max_holdings": max_holdings,
        "col2": "1M", "col3": "3M", "news_feed": True,
    })
    config["rankings"] = rankings
    _append_to_order(config, "ranking", name)
    return config


def remove_ranking(config: dict, ranking_id: int) -> dict:
    for r in config.get("rankings", []):
        if r["ranking_id"] == ranking_id:
            _remove_from_order(config, "ranking", r["name"])
            break
    config["rankings"] = [
        r for r in config.get("rankings", []) if r["ranking_id"] != ranking_id
    ]
    return config


def move_ranking(config: dict, index: int, direction: int) -> dict:
    rankings = config.get("rankings", [])
    new_index = index + direction
    if 0 <= new_index < len(rankings):
        rankings[index], rankings[new_index] = rankings[new_index], rankings[index]
    config["rankings"] = rankings
    return config


# ---- Trader Accounts ----


def add_trader_account(config: dict, name: str) -> dict:
    """Add a new empty trader account."""
    accounts = config.setdefault("trader_accounts", [])
    if any(a["name"] == name for a in accounts):
        return config
    accounts.append({"name": name, "strategies": []})
    return config


def remove_trader_account(config: dict, name: str) -> dict:
    """Remove a trader account by name."""
    config["trader_accounts"] = [
        a for a in config.get("trader_accounts", []) if a["name"] != name
    ]
    return config


def add_trader_strategy(config: dict, account_name: str, strategy_id: int, strategy_name: str) -> dict:
    """Add a strategy to a trader account."""
    for acct in config.get("trader_accounts", []):
        if acct["name"] == account_name:
            if any(s["id"] == strategy_id for s in acct["strategies"]):
                return config
            acct["strategies"].append({"id": strategy_id, "name": strategy_name})
            break
    return config


def remove_trader_strategy(config: dict, account_name: str, strategy_id: int) -> dict:
    """Remove a strategy from a trader account."""
    for acct in config.get("trader_accounts", []):
        if acct["name"] == account_name:
            acct["strategies"] = [
                s for s in acct["strategies"] if s["id"] != strategy_id
            ]
            break
    return config


def rename_trader_account(config: dict, old_name: str, new_name: str) -> dict:
    """Rename a trader account."""
    if old_name == new_name:
        return config
    # Guard against duplicates
    if any(a["name"] == new_name for a in config.get("trader_accounts", [])):
        return config
    for acct in config.get("trader_accounts", []):
        if acct["name"] == old_name:
            acct["name"] = new_name
            break
    return config


def update_trader_strategy(config: dict, account_name: str, old_id: int,
                           new_id: int, new_name: str) -> dict:
    """Update a strategy's name and/or ID within a trader account."""
    for acct in config.get("trader_accounts", []):
        if acct["name"] == account_name:
            for strat in acct["strategies"]:
                if strat["id"] == old_id:
                    strat["id"] = new_id
                    strat["name"] = new_name
                    break
            break
    return config


def move_trader_account(config: dict, index: int, direction: int) -> dict:
    """Move a trader account up (-1) or down (+1)."""
    accounts = config.get("trader_accounts", [])
    new_index = index + direction
    if 0 <= new_index < len(accounts):
        accounts[index], accounts[new_index] = accounts[new_index], accounts[index]
    config["trader_accounts"] = accounts
    return config


# ---- Sidebar Order ----


def move_sidebar_order(config: dict, index: int, direction: int) -> dict:
    """Move a sidebar order entry up (-1) or down (+1)."""
    order = config.get("sidebar_order", [])
    new_index = index + direction
    if 0 <= new_index < len(order):
        order[index], order[new_index] = order[new_index], order[index]
    config["sidebar_order"] = order
    return config
