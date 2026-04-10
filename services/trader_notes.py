"""Persistence for trader notes and recommendation data."""

import json
import os
from datetime import datetime, timezone

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
NOTES_PATH = os.path.join(_BASE_DIR, "trader_notes.json")
TRADER_DATA_PATH = os.path.join(_BASE_DIR, "trader_data.json")
RANKING_DATA_PATH = os.path.join(_BASE_DIR, "ranking_data.json")
STRATEGY_HOLDINGS_PATH = os.path.join(_BASE_DIR, "strategy_holdings.json")
SCREEN_HOLDINGS_PATH = os.path.join(_BASE_DIR, "screen_holdings.json")


# ---- Notes persistence ----


def load_notes() -> dict:
    """Load notes from disk.

    Returns {(strategy_id, ticker): note_text}.
    """
    if not os.path.exists(NOTES_PATH):
        return {}
    try:
        with open(NOTES_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {
            (int(k.split("|", 1)[0]), k.split("|", 1)[1]): v
            for k, v in raw.items()
        }
    except Exception:
        return {}


def save_notes(notes: dict) -> None:
    """Save notes to disk. Expects {(strategy_id, ticker): note_text}."""
    raw = {f"{sid}|{ticker}": text for (sid, ticker), text in notes.items()}
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


def set_note(notes: dict, strategy_id: int, ticker: str, text: str) -> dict:
    """Set or remove a note. Returns updated notes dict."""
    if text.strip():
        notes[(strategy_id, ticker)] = text.strip()
    else:
        notes.pop((strategy_id, ticker), None)
    save_notes(notes)
    return notes


def get_noted_tickers(notes: dict, strategy_id: int) -> set:
    """Get all tickers that have notes for a given strategy."""
    return {ticker for (sid, ticker) in notes if sid == strategy_id}


# ---- Trader data (recommendations) persistence ----


def save_trader_data(trader_data: dict, last_update: datetime | None) -> None:
    """Save fetched recommendations to disk so they survive session restarts.

    trader_data: {strategy_id_int: {ranks, op, recs, name, account}}
    """
    serializable = {}
    for sid, sdata in trader_data.items():
        serializable[str(sid)] = {
            "ranks": sdata.get("ranks", []),
            "op": sdata.get("op"),
            "recs": [
                {
                    "rec": r["rec"],
                    "rank": r["rank"],
                    "is_dummy": r.get("is_dummy", False),
                }
                for r in sdata.get("recs", [])
            ],
            "name": sdata.get("name", ""),
            "account": sdata.get("account", ""),
        }
    payload = {
        "last_update": last_update.isoformat() if last_update else None,
        "strategies": serializable,
    }
    with open(TRADER_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_trader_data() -> tuple[dict, datetime | None]:
    """Load saved recommendations from disk.

    Returns (trader_data_dict, last_update_datetime).
    """
    if not os.path.exists(TRADER_DATA_PATH):
        return {}, None
    try:
        with open(TRADER_DATA_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)

        last_update = None
        if payload.get("last_update"):
            last_update = datetime.fromisoformat(payload["last_update"])

        trader_data = {}
        for sid_str, sdata in payload.get("strategies", {}).items():
            sid = int(sid_str)
            trader_data[sid] = {
                "ranks": sdata.get("ranks", []),
                "op": sdata.get("op"),
                "recs": [
                    {
                        "rec": r["rec"],
                        "rank": r["rank"],
                        "is_dummy": r.get("is_dummy", False),
                    }
                    for r in sdata.get("recs", [])
                ],
                "name": sdata.get("name", ""),
                "account": sdata.get("account", ""),
            }
        return trader_data, last_update
    except Exception:
        return {}, None


# ---- Ranking data persistence ----


def save_ranking_data(
    ranking_data: dict,
    nodes_data: dict | None,
    last_update: datetime | None,
) -> None:
    """Save ranking holdings and composite node scores to disk.

    ranking_data: {ranking_id_int: [ticker_str, ...]}
    nodes_data:   {ranking_id_int: {names: [...], weights: [...], scores: {ticker: [float, ...]}}}
    """
    payload = {
        "last_update": last_update.isoformat() if last_update else None,
        "rankings": {str(k): v for k, v in ranking_data.items()},
        "nodes": {str(k): v for k, v in (nodes_data or {}).items()},
    }
    with open(RANKING_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_ranking_data() -> tuple[dict, dict, datetime | None]:
    """Load saved ranking holdings and composite node scores from disk.

    Returns (ranking_data, nodes_data, last_update_datetime).
    """
    if not os.path.exists(RANKING_DATA_PATH):
        return {}, {}, None
    try:
        with open(RANKING_DATA_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        last_update = None
        if payload.get("last_update"):
            last_update = datetime.fromisoformat(payload["last_update"])
        ranking_data = {}
        for rid_str, tickers in payload.get("rankings", {}).items():
            ranking_data[int(rid_str)] = tickers
        nodes_data = {}
        for rid_str, ndata in payload.get("nodes", {}).items():
            nodes_data[int(rid_str)] = ndata
        return ranking_data, nodes_data, last_update
    except Exception:
        return {}, {}, None


# ---- Strategy holdings persistence ----


def _save_holdings(path: str, data: dict, last_update: datetime | None) -> None:
    """Generic save: {int_id: [ticker, ...]} → JSON file."""
    payload = {
        "last_update": last_update.isoformat() if last_update else None,
        "holdings": {str(k): v for k, v in data.items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load_holdings(path: str) -> tuple[dict, datetime | None]:
    """Generic load: JSON file → {int_id: [ticker, ...]}."""
    if not os.path.exists(path):
        return {}, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        last_update = None
        if payload.get("last_update"):
            last_update = datetime.fromisoformat(payload["last_update"])
        data = {}
        for id_str, tickers in payload.get("holdings", {}).items():
            data[int(id_str)] = tickers
        return data, last_update
    except Exception:
        return {}, None


def save_strategy_holdings(data: dict, last_update: datetime | None) -> None:
    """Save strategy holdings to disk. {strategy_id: [ticker, ...]}"""
    _save_holdings(STRATEGY_HOLDINGS_PATH, data, last_update)


def load_strategy_holdings() -> tuple[dict, datetime | None]:
    """Load strategy holdings from disk."""
    return _load_holdings(STRATEGY_HOLDINGS_PATH)


def save_screen_holdings(data: dict, last_update: datetime | None) -> None:
    """Save screen holdings to disk. {screen_id: [ticker, ...]}"""
    _save_holdings(SCREEN_HOLDINGS_PATH, data, last_update)


def load_screen_holdings() -> tuple[dict, datetime | None]:
    """Load screen holdings from disk."""
    return _load_holdings(SCREEN_HOLDINGS_PATH)
