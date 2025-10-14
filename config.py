"""
Configuration module for Supabase connection and environment variables.
Supports both Streamlit Secrets (for cloud deployment) and .env file (for local development).
"""
import os
from dotenv import load_dotenv

# Try to import streamlit for secrets support
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

# Load .env file for local development
load_dotenv()

# Priority: Streamlit Secrets > Environment Variables (.env)
if HAS_STREAMLIT:
    try:
        SUPABASE_URL = st.secrets.get("PUBLIC_SUPABASE_URL", os.getenv("PUBLIC_SUPABASE_URL"))
        SUPABASE_KEY = st.secrets.get("PUBLIC_SUPABASE_ANON_KEY", os.getenv("PUBLIC_SUPABASE_ANON_KEY"))
    except Exception:
        # Fallback to environment variables if secrets not available
        SUPABASE_URL = os.getenv("PUBLIC_SUPABASE_URL")
        SUPABASE_KEY = os.getenv("PUBLIC_SUPABASE_ANON_KEY")
else:
    SUPABASE_URL = os.getenv("PUBLIC_SUPABASE_URL")
    SUPABASE_KEY = os.getenv("PUBLIC_SUPABASE_ANON_KEY")

# 설정 검증
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Supabase credentials not found. "
        "Please ensure PUBLIC_SUPABASE_URL and PUBLIC_SUPABASE_ANON_KEY are set in:\n"
        "- Streamlit Secrets (for cloud deployment), or\n"
        "- .env file (for local development)"
    )
