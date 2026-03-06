"""Fetch latest topics from the Portfolio123 Discourse community forum."""

import html as html_mod
from datetime import datetime, timezone

import requests
import streamlit as st

FORUM_BASE = "https://community.portfolio123.com"


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_categories() -> dict[int, dict]:
    """Return {category_id: {"name": ..., "color": ...}} map."""
    try:
        resp = requests.get(f"{FORUM_BASE}/categories.json", timeout=10)
        resp.raise_for_status()
        cats = resp.json().get("category_list", {}).get("categories", [])
        return {
            c["id"]: {"name": c["name"], "color": c.get("color", "888888")}
            for c in cats
        }
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_forum_posts(count: int = 10) -> list[dict]:
    """Fetch the latest *count* topics from the P123 community forum.

    Returns a list of dicts with keys:
        id, title, slug, url, category_name, category_color,
        reply_count, views, like_count, time_ago
    """
    try:
        resp = requests.get(f"{FORUM_BASE}/latest.json", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    topics = data.get("topic_list", {}).get("topics", [])
    categories = _fetch_categories()

    results: list[dict] = []
    for t in topics:
        # Skip pinned welcome / meta topics
        if t.get("pinned"):
            continue

        cat_id = t.get("category_id")
        cat = categories.get(cat_id, {"name": "", "color": "888888"})

        results.append(
            {
                "id": t["id"],
                "title": html_mod.unescape(t.get("fancy_title") or t.get("title", "")),
                "slug": t.get("slug", ""),
                "url": f"{FORUM_BASE}/t/{t.get('slug', '')}/{t['id']}",
                "category_name": cat["name"],
                "category_color": cat["color"],
                "reply_count": t.get("reply_count", 0),
                "views": t.get("views", 0),
                "like_count": t.get("like_count", 0),
                "time_ago": _time_ago(t.get("last_posted_at", "")),
            }
        )
        if len(results) >= count:
            break

    return results


def _time_ago(iso_str: str) -> str:
    """Convert ISO timestamp to human-friendly relative time."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        if days < 30:
            return f"{days}d"
        months = days // 30
        return f"{months}mo"
    except Exception:
        return ""
