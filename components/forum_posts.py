"""Render latest Portfolio123 community forum posts."""

import html
import streamlit as st
from utils.constants import COLORS_DARK, COLORS_LIGHT
from services.forum_data import fetch_forum_posts


def render_forum_posts(n: int = 4):
    """Render the N most recent forum topics as a compact list."""
    config = st.session_state.get("config", {})
    n = config.get("settings", {}).get("forum_post_count", n)

    posts = fetch_forum_posts(count=n)
    if not posts:
        return

    theme = st.session_state.get("theme", "dark")
    colors = COLORS_DARK if theme == "dark" else COLORS_LIGHT

    # Section header with link to full forum
    st.markdown(
        f'<div class="forum-header">'
        f'<span>Community</span>'
        f'<a href="https://community.portfolio123.com/" target="_blank" '
        f'class="forum-header-link" title="Open forum">'
        f'&#8599;</a>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Render all rows as a single HTML block
    rows: list[str] = []
    for post in posts:
        title_escaped = html.escape(post["title"])
        cat_color = f"#{post['category_color']}"
        cat_name = html.escape(post["category_name"])

        cat_badge = (
            f'<span class="forum-category" '
            f'style="background:{cat_color}22;color:{cat_color};'
            f'border:1px solid {cat_color}44;">{cat_name}</span>'
        )

        title_link = (
            f'<a href="{post["url"]}" target="_blank" '
            f'class="forum-title" title="{title_escaped}">{title_escaped}</a>'
        )

        replies = post["reply_count"]
        reply_html = (
            f'<span class="forum-meta">💬&thinsp;{replies}</span>'
            if replies > 0
            else '<span class="forum-meta"></span>'
        )

        time_html = f'<span class="forum-meta forum-time">{post["time_ago"]}</span>'

        rows.append(
            f'<div class="forum-row">'
            f'{cat_badge}{title_link}{reply_html}{time_html}'
            f'</div>'
        )

    st.markdown("\n".join(rows), unsafe_allow_html=True)
