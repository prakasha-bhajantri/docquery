import streamlit as st
import requests
import os
from typing import List, Tuple

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000" # Your FastAPI server address

# 1. UI Helper Functions (to interact with FastAPI)

@st.cache_data(show_spinner=False)
def get_indexed_documents() -> Tuple[List[str], str]:
    """Fetches the list of indexed documents and the selected document from the API."""
    try:
        # NOTE: This function is cached, so it won't run unless its cache is cleared.
        response = requests.get(f"{API_URL}/documents")
        response.raise_for_status()
        data = response.json()
        doc_list = data.get("documents", [])
        selected_doc = data.get("selected_document", "")
        return doc_list, selected_doc 
    except Exception:
        # Return empty list and empty string on error
        return [], "" 

def format_status(filename: str, message: str, color: str = 'red') -> str:
    """Formats the status message, coloring only the filename."""
    # This creates the HTML span tag around the filename
    colored_filename = f"<span style='color:{color};'>**{filename}**</span>"
    
    # We use f-strings to find and replace the plain filename with the colored version
    return message.replace(f"**{filename}**", colored_filename)

def set_initial_state():
    """Initializes Streamlit session state variables."""
    # This check ensures we don't re-initialize state variables on every rerun
    if 'doc_list' not in st.session_state or 'selected_doc' not in st.session_state:
        st.session_state.doc_list, st.session_state.selected_doc = get_indexed_documents()
        
        # Ensure a default selection is made if documents exist but none is active
        if st.session_state.doc_list and not st.session_state.selected_doc:
            st.session_state.selected_doc = st.session_state.doc_list[0]
            # Call the select_document API to set it active on the server
            select_document_api(st.session_state.selected_doc) 

    if 'upload_status' not in st.session_state:
        st.session_state.upload_status = "Ready to index."
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
        
def select_document_api(filename: str):
    """Sets the active document for QA via the API and updates state."""
    if not filename:
        st.session_state.upload_status = "Please select a file."
        return

    try:
        # NOTE: We skip clearing the cache here since selection doesn't change the list
        response = requests.post(f"{API_URL}/select_document", json={"filename": filename})
        response.raise_for_status()
        st.session_state.selected_doc = filename # Update local state
        message = f"Document **{filename}** set as active for QA and loaded from index."
        st.session_state.upload_status = format_status(filename, message, 'red')
        # st.session_state.upload_status = f"Document **{filename}** set as active for QA and loaded from index."
        
    except Exception as e:
        # This is where your 404 error is coming from. Check your FastAPI backend!
        st.session_state.upload_status = f"Error selecting document: {e}"

def upload_and_index_action(uploaded_file):
    """Uploads file to API, refreshes state, and sets new file as active."""
    if uploaded_file is None:
        st.session_state.upload_status = "Please select a file to upload."
        return
    
    try:
        # Save uploaded file temporarily for FastAPI call
        temp_dir = "/tmp/rag_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        original_filename = uploaded_file.name
        
        # FastAPI expects the file via a multipart form
        with open(file_path, "rb") as f:
            files = {"file": (original_filename, f, "multipart/form-data")}
            response = requests.post(f"{API_URL}/upload", files=files)
            response.raise_for_status() 
            
        # message = response.json().get("status", "Indexing complete.")
        # We need the filename here
        original_filename = uploaded_file.name
        
        # The success message needs to be adjusted to include the filename for coloring
        full_message = f"Success! **{original_filename}** indexing complete."
        
        # MODIFIED LINE: Format the status to color the filename red
        st.session_state.upload_status = format_status(original_filename, full_message, 'red')        
        # st.session_state.upload_status = f"Success! {message}"
        
        # FIX: CLEAR CACHE to force get_indexed_documents to re-fetch the new list
        get_indexed_documents.clear()
        
        # After successful upload, refresh the full list and set the new file as active
        new_doc_list, _ = get_indexed_documents()
        
        # Update doc_list and explicitly set the newly uploaded file as selected
        st.session_state.doc_list = new_doc_list
        select_document_api(original_filename) # This will update selected_doc and status

    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        st.session_state.upload_status = f"Error indexing file: {error_detail}"
    except Exception as e:
        st.session_state.upload_status = f"An unexpected error occurred: {type(e).__name__}: {e}"
        # Clean up temp file on failure too
        if os.path.exists(file_path):
             os.remove(file_path)


def delete_document_action(filename: str):
    """Deletes the selected document from the index and updates state."""
    if not filename:
        st.session_state.upload_status = "Please select a file to delete."
        return
        
    try:
        # NOTE: This is where your 404 error for DELETE is likely coming from. Check FastAPI!
        response = requests.delete(f"{API_URL}/document/{filename}")
        response.raise_for_status()
        
        message = f"Document **{filename}** deleted successfully."
        st.session_state.upload_status = format_status(filename, message, 'red')
        # st.session_state.upload_status = f"Document **{filename}** deleted successfully."

        # FIX: CLEAR CACHE to force get_indexed_documents to re-fetch the new list
        get_indexed_documents.clear()
        
        # After successful deletion, refresh the document list
        st.session_state.doc_list, _ = get_indexed_documents()
        
        # Update selection if the deleted file was the active one
        if st.session_state.selected_doc == filename:
            st.session_state.selected_doc = st.session_state.doc_list[0] if st.session_state.doc_list else ""
            if st.session_state.selected_doc:
                 select_document_api(st.session_state.selected_doc)
            else:
                 st.session_state.upload_status += " (Active document cleared)."

    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        st.session_state.upload_status = f"Error deleting file: {error_detail}"
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

# 0. Setup Initial State
set_initial_state()

st.title("DocQuery: Chat with your Documents")

# 1. Sidebar for Document Management
with st.sidebar:
    # st.header("📄 Document Management")
    
    # 1.1 Document Selector/Deleter
    st.subheader("📚 Select Active Document")
    
    # Determine the index of the currently selected document for the selectbox
    current_index = 0
    # FIX: Ensure we only look for the index if the list is not empty
    if st.session_state.doc_list and st.session_state.selected_doc in st.session_state.doc_list:
        current_index = st.session_state.doc_list.index(st.session_state.selected_doc)
    
    # Streamlit Selectbox (Dropdown equivalent)
    # The key is used to detect changes and call the selection API
    st.selectbox(
        label="Select Indexed Document to Chat With",
        options=st.session_state.doc_list,
        index=current_index, # Uses the index of the active document
        key='doc_selector',
        # on_change logic ensures that when the user changes the dropdown, the API is called
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
    
    # 1.2 File Upload Section
    st.subheader("⬆️ Upload New Document")
    
    # Streamlit file uploader (compact by default)
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
    
    # Status Box (Uses st.info or st.code for the multiline box)
    st.subheader("Indexing Status")
    # st.code(st.session_state.upload_status, language='text')
    # st.markdown(st.session_state.upload_status)
    # st.markdown(f"<span style='color:red;'>{st.session_state.upload_status}</span>", unsafe_allow_html=True)
    st.markdown(st.session_state.upload_status, unsafe_allow_html=True)


# 2. Main Chat Interface
# st.header("💬 Chat with Indexed Documents")

# Initialize chat history if not present
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input logic
if prompt := st.chat_input(f"Ask about: {st.session_state.selected_doc if st.session_state.selected_doc else 'No Document Selected'}..."):
    # 1. User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. API Call (RAG Response)
    response_text = chat_with_api_action(prompt)

    # 3. Assistant Message
    with st.chat_message("assistant"):
        st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})