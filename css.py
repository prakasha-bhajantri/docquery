# --- 0. CUSTOM CSS INJECTION ---
import streamlit as st
def inject_custom_css():
    st.markdown("""
        <style>
        /* 1. FIXED TITLE AT TOP - Always visible */
        [data-testid="stHeader"] {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 9999;
            background-color: white;
            padding: 1rem 2rem;
            border-bottom: 1px solid #e0e0e0;
        }
        /* Push main content below fixed header */
        .block-container {
            padding-top: 6rem !important;
        }

        /* 2. WIDER CHAT PANEL */
        section.main > div:has(> [data-testid="stChatMessage"]) {
            max-width: 90% !important;
            margin: 0 auto;
        }
        /* Alternative fallback for newer Streamlit versions */
        [data-testid="stAppViewContainer"] > .main > div {
            max-width: 90% !important;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        /* 3. USER MESSAGES TO RIGHT */
        [data-testid="stChatMessage"][data-role="user"] {
            flex-direction: row-reverse;
        }
        [data-testid="stChatMessage"][data-role="user"] .stMarkdown {
            background-color: #dcf8c6 !important;
            padding: 12px 16px;
            border-radius: 18px 18px 4px 18px;
            max-width: 80%;
            margin-left: auto !important;
        }

        /* 4. ASSISTANT MESSAGES TO LEFT */
        [data-testid="stChatMessage"][data-role="assistant"] .stMarkdown {
            background-color: #f0f2f6 !important;
            padding: 12px 16px;
            border-radius: 18px 18px 18px 4px;
            max-width: 80%;
            margin-right: auto !important;
        }

        /* Optional: nicer chat container spacing */
        .stChatMessage {
            margin-bottom: 1.5rem;
        }
        </style>
        """, unsafe_allow_html=True)