from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="ToolAgent · Engineering Support", page_icon="◆", layout="wide", initial_sidebar_state="collapsed")

template = (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")
html = template.replace("__API_URL__", json.dumps(os.getenv("API_URL", "http://localhost:8000")))

st.markdown(
    """
    <style>
      #MainMenu, header, footer {display:none !important}
      .stApp {background:#07110f}
      .block-container {padding:0 !important; max-width:none !important}
      iframe {display:block}
    </style>
    """,
    unsafe_allow_html=True,
)
components.html(html, height=1040, scrolling=True)

