import streamlit as st
import requests
import os
from css import a

# --- Configuration ---
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="DocQuery RAG Chatbot",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# CUSTOM CSS (Strict Positioning)
# =========================
st.markdown(a, unsafe_allow_html=True)


# --- Session State Initialization ---
if 'index_name' not in st.session_state:
    st.session_state.index_name = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []


## ------------------------------------------------
## API Functions
## ------------------------------------------------
def upload_file_to_api(uploaded_file):
    url = f"{API_BASE_URL}/upload"
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    try:
        with st.spinner("Uploading..."):
            r = requests.post(url, files=files, timeout=300)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return {}

def query_api(q, idx_name):
    try:
        r = requests.post(f"{API_BASE_URL}/query", 
                          json={"question": q, "index_name": idx_name, "top_k": 4}, 
                          timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"answer": f"Error: {e}", "retrieved": []}


## ------------------------------------------------
## Sidebar
## ------------------------------------------------
with st.sidebar:
    st.header("1. Upload Document")
    uploaded_file = st.file_uploader("PDF, DOCX, TXT", type=["pdf","docx","txt"])

    if uploaded_file and not st.session_state.index_name:
        if st.button("Index File", type="primary", use_container_width=True):
            res = upload_file_to_api(uploaded_file)
            if "index_name" in res:
                st.session_state.index_name = res["index_name"]
                st.success("Indexed successfully!")
                st.rerun()
    
    if st.session_state.index_name:
        st.success(f"Active Index: {st.session_state.index_name}")
        if st.button("Reset Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.index_name = None
            st.rerun()


## ------------------------------------------------
## Main Chat Interface
## ------------------------------------------------

# Helper to push content down
st.write("")

if not st.session_state.index_name:
    st.markdown("<h3 style='text-align: center; margin-top: 20%; color: #666;'>Please upload a document to start chatting.</h3>", unsafe_allow_html=True)
else:
    # Display Chat History
    for role, msg, sources in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)
            # if sources:
            #     with st.expander(f"📚 Sources ({len(sources)})"):
            #         for i, s in enumerate(sources):
            #             file = s.get("metadata", {}).get("source", "Unknown")
            #             st.caption(f"Source {i+1} • {file}")
            #             st.code(s.get("text", "")[:300] + "...", language=None)

    # Chat Input
    if prompt := st.chat_input("Ask a question..."):
        # User
        st.session_state.chat_history.append(("user", prompt, None))
        with st.chat_message("user"):
            st.markdown(prompt)

        # Bot
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                res = query_api(prompt, st.session_state.index_name)
                answer = res.get("answer", "No answer generated.")
                docs = res.get("retrieved", [])
            
            st.markdown(answer)
            # if docs:
            #     with st.expander(f"📚 Sources ({len(docs)})"):
            #         for i, s in enumerate(docs):
            #             file = s.get("metadata", {}).get("source", "Unknown")
            #             st.caption(f"Source {i+1} • {file}")
            #             st.code(s.get("text", "")[:300] + "...", language=None)
        
        st.session_state.chat_history.append(("assistant", answer, docs))