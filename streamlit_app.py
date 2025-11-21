import streamlit as st
import requests
import os
from typing import List, Tuple
from dotenv import load_dotenv

# Load environment variables (CRITICAL: Must be run before initializing NVIDIA classes)
load_dotenv() 

API_URL = st.secrets.get("API_URL", "http://127.0.0.1:8000")

# --- CONFIGURATION ---
# API_URL = "http://127.0.0.1:8000" # Your FastAPI server address

# API_URL = os.getenv("API_URL")

# --- 0. CUSTOM CSS INJECTION ---
def inject_custom_css():
    st.markdown("""
        <style>
        /* ==== FIXED CUSTOM HEADER WITH TITLE ==== */
        .fixed-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 70px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            z-index: 9999;
            display: flex;
            align-items: center;
            padding: 0 2rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            color: white;
            font-size: 1.8rem;
            font-weight: 700;
        }
        /* Keep Streamlit's top-right icons visible */
        [data-testid="stHeader"]::before {
            content: "DocQuery - Chat with your Documents";
            position: absolute;
            left: 5rem;
            top: 50%;
            transform: translateY(-50%);
            color: white;
            font-size: 1.8rem;
            font-weight: 700;
            z-index: 9999;
        }

        /* Push entire app content down below fixed header */
        .block-container {
            padding-top: 90px !important;
        }

        /* ==== WIDTH CONTROL FOR WIDE LAYOUT ==== */
        /* Main container with controlled max-width */
        .main .block-container {
        max-width: 1400px !important;
        padding-left: 2rem;
        padding-right: 2rem;
        margin: 0 auto !important;
        }

        /* Chat area specific width control */
        [data-testid="stVerticalBlock"] {
        max-width: 1000px !important;
        margin: 0 auto !important;
        }


        /* When sidebar is collapsed, expand slightly */
        [data-testid="stSidebar"][aria-expanded="false"] ~ .main .block-container {
        max-width: 1600px !important;
        }

        [data-testid="stSidebar"][aria-expanded="false"] ~ .main [data-testid="stVerticalBlock"] {
        max-width: 1200px !important;
        }

        [data-testid="stSidebar"][aria-expanded="false"] ~ .main [data-testid="stChatInput"] {
        max-width: 1200px !important;
        }

        </style>
        """, unsafe_allow_html=True)

# 1. UI Helper Functions (to interact with FastAPI)

@st.cache_data(show_spinner=False)
def get_indexed_documents() -> Tuple[List[str], str]:
    """Fetches the list of indexed documents and the selected document from the API."""
    try:
        response = requests.get(f"{API_URL}/documents")
        response.raise_for_status()
        data = response.json()
        doc_list = data.get("documents", [])
        selected_doc = data.get("selected_document", "")
        return doc_list, selected_doc 
    except Exception:
        return [], "" 

def format_status(filename: str, message: str, color: str = 'red') -> str:
    """Formats the status message, coloring only the filename."""
    colored_filename = f"<span style='color:{color};'>**{filename}**</span>"
    return message.replace(f"**{filename}**", colored_filename)

def set_initial_state():
    """Initializes Streamlit session state variables."""
    if 'doc_list' not in st.session_state or 'selected_doc' not in st.session_state:
        st.session_state.doc_list, st.session_state.selected_doc = get_indexed_documents()
        
        if st.session_state.doc_list and not st.session_state.selected_doc:
            st.session_state.selected_doc = st.session_state.doc_list[0]
            select_document_api(st.session_state.selected_doc) 

    if 'upload_status' not in st.session_state:
        st.session_state.upload_status = "Ready to index."
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []

def select_document_api(filename: str):
    """Sets the active document for QA via the API and updates state."""
    if not filename:
        st.session_state.upload_status = "Please select a file."
        return

    try:
        response = requests.post(f"{API_URL}/select_document", json={"filename": filename})
        response.raise_for_status()
        st.session_state.selected_doc = filename
        message = f"Document **{filename}** set as active for QA and loaded from index."
        st.session_state.upload_status = format_status(filename, message, 'red')
        
    except Exception as e:
        st.session_state.upload_status = f"Error selecting document: {e}"

def upload_and_index_action(uploaded_file):
    """Uploads file to API, refreshes state, and sets new file as active."""
    if uploaded_file is None:
        st.session_state.upload_status = "Please select a file to upload."
        return
    
    try:
        temp_dir = "/tmp/rag_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        original_filename = uploaded_file.name
        
        with open(file_path, "rb") as f:
            files = {"file": (original_filename, f, "multipart/form-data")}
            response = requests.post(f"{API_URL}/upload", files=files)
            response.raise_for_status() 
            
        
        full_message = f"Success! **{original_filename}** indexing complete."
        st.session_state.upload_status = format_status(original_filename, full_message, 'red')        
        
        get_indexed_documents.clear()
        
        new_doc_list, _ = get_indexed_documents()
        
        st.session_state.doc_list = new_doc_list
        select_document_api(original_filename)

    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        st.session_state.upload_status = f"Error indexing file: {error_detail}"
    except Exception as e:
        st.session_state.upload_status = f"An unexpected error occurred: {type(e).__name__}: {e}"
        if os.path.exists(file_path):
             os.remove(file_path)


def delete_document_action(filename: str):
    """Deletes the selected document from the index and updates state."""
    if not filename:
        st.session_state.upload_status = "Please select a file to delete."
        return
        
    try:
        response = requests.delete(f"{API_URL}/document/{filename}")
        response.raise_for_status()
        
        message = f"Document **{filename}** deleted successfully."
        st.session_state.upload_status = format_status(filename, message, 'red')

        get_indexed_documents.clear()
        
        st.session_state.doc_list, _ = get_indexed_documents()
        
        if st.session_state.selected_doc == filename:
            st.session_state.selected_doc = st.session_state.doc_list[0] if st.session_state.doc_list else ""
            if st.session_state.selected_doc:
                 select_document_api(st.session_state.selected_doc)
            else:
                 clear_message = f" (Active document cleared)."
                 st.session_state.upload_status += clear_message


    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        error_message = f"Error deleting file: **{filename}**. Details: {error_detail}"
        st.session_state.upload_status = format_status(filename, error_message, 'red')
    except Exception as e:
        st.session_state.upload_status = f"An unexpected error occurred during deletion: {e}"

def chat_with_api_action(message) -> str:
    """Sends user message to the FastAPI chat endpoint."""
    try:
        if not st.session_state.selected_doc:
            return "Please select an active document before chatting."
            
        response = requests.post(
            f"{API_URL}/query", 
            json={"query": message}
        )
        response.raise_for_status()
        return response.json().get("response", "Error: No response from RAG service.")
    except Exception as e:
        return f"An error occurred while querying the RAG API. Is the FastAPI backend running? Details: {e}"

# --- STREAMLIT APP LAYOUT ---

# Set page config for better layout control
st.set_page_config(
    page_title="DocQuery - Chat with your Documents",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 0. Setup Initial State
set_initial_state()

# Inject Custom CSS
inject_custom_css()

# 1. Main Title

# 2. Sidebar for Document Management
with st.sidebar:
    st.header("📄 Document Management")
    
    # 2.1 Document Selector/Deleter
    st.subheader("📚 Select Active Document")
    
    current_index = 0
    if st.session_state.doc_list and st.session_state.selected_doc in st.session_state.doc_list:
        current_index = st.session_state.doc_list.index(st.session_state.selected_doc)
    
    st.selectbox(
        label="Select Indexed Document to Chat With",
        options=st.session_state.doc_list,
        index=current_index,
        key='doc_selector',
        on_change=lambda: select_document_api(st.session_state.doc_selector)
    )

    # Delete Button
    st.button(
        "Delete Selected Document 🗑️", 
        type="primary", 
        on_click=delete_document_action, 
        args=(st.session_state.doc_selector,),
        disabled=not st.session_state.doc_list
    )
    
    st.markdown("---")
    
    # 2.2 File Upload Section
    st.subheader("⬆️ Upload New Document")
    
    uploaded_file = st.file_uploader(
        "Upload Document (.pdf, .txt, .docx)",
        type=["pdf", "txt", "docx"],
        key="file_uploader"
    )
    
    st.button(
        "Upload and Index", 
        on_click=upload_and_index_action, 
        args=(uploaded_file,)
    )
    
    # Status Message Display
    st.subheader("Indexing Status")
    st.markdown(st.session_state.upload_status, unsafe_allow_html=True)


# 3. Main Chat Interface
# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input(f"Ask about: {st.session_state.selected_doc if st.session_state.selected_doc else 'No Document Selected'}..."):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Get assistant response
    response = chat_with_api_action(prompt)
    
    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(response)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})