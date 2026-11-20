from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="☕ 카페 러쉬!", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>.block-container{padding:.5rem 1rem 0} header,footer{visibility:hidden}</style>",
            unsafe_allow_html=True)

# 게임 화면/로직은 game.html (Supabase REST + RPC 호출), DB 스키마·함수는 migration.sql
html = (Path(__file__).parent / "game.html").read_text(encoding="utf-8")
components.html(html, height=760, scrolling=False)
