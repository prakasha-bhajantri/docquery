import gradio as gr
import requests
import json
import os
from typing import List, Tuple

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000" # Your FastAPI server address

# 1. UI Helper Functions (to interact with FastAPI)
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
        # Return empty list and empty string on error
        return [], "" 

# NOTE: update_doc_display is retained but currently unused in the simplified UI
def update_doc_display(doc_list: List[str], selected_doc: str) -> str:
    """Formats the document list for display with a selection indicator."""
    if not doc_list:
        return "No documents indexed. Upload a file to begin chatting."
        
    display_text = "Indexed Documents:\n"
    for doc in doc_list:
        # Add an indicator to the selected document
        indicator = "✅" if doc == selected_doc else "◻️"
        display_text += f"{indicator} **{doc}**\n"
        
    return display_text

def upload_and_index(file) -> Tuple[str, List[str], str, None]:
    """Uploads a file to the API for indexing."""
    if file is None:
        doc_list, selected_doc = get_indexed_documents()
        return "Please select a file to upload.", doc_list, selected_doc, None
    
    file_path = file.name
    
    try:
        original_filename = os.path.basename(file_path) 
        
        # FastAPI expects the file via a multipart form
        with open(file_path, "rb") as f:
            files = {"file": (original_filename, f, "multipart/form-data")}
            response = requests.post(f"{API_URL}/upload", files=files)
            response.raise_for_status() 
            
        message = response.json().get("status", "Indexing complete.")
        
        # After successful upload, refresh the list and selected doc state
        doc_list, selected_doc = get_indexed_documents()
        
        # Return 4 outputs: Status, Doc List State, Selected Doc State, Cleared File Component (None)
        return f"Success! {message}", doc_list, selected_doc, None
            
    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        doc_list, selected_doc = get_indexed_documents()
        return f"Error indexing file: {error_detail}", doc_list, selected_doc, None
    except Exception as e:
        doc_list, selected_doc = get_indexed_documents()
        return f"An unexpected error occurred: {type(e).__name__}: {e}", doc_list, selected_doc, None

def select_document(filename: str) -> Tuple[str, List[str], str]:
    """Sets the active document for QA."""
    if not filename:
        doc_list, selected_doc = get_indexed_documents()
        return "Please select a file.", doc_list, selected_doc
        
    try:
        response = requests.post(f"{API_URL}/select_document", json={"filename": filename})
        response.raise_for_status()
        
        # Re-fetch the list to get the new selected document state
        doc_list, selected_doc = get_indexed_documents()
        
        return f"Document **{filename}** set as active for QA.", doc_list, selected_doc
    except Exception as e:
        doc_list, selected_doc = get_indexed_documents()
        return f"Error selecting document: {e}", doc_list, selected_doc


def delete_document(filename: str) -> Tuple[str, List[str], str]:
    """Deletes the selected document from the index."""
    if not filename:
        doc_list, selected_doc = get_indexed_documents()
        return "Please select a file to delete.", doc_list, selected_doc
        
    try:
        # Use DELETE method for deletion endpoint
        response = requests.delete(f"{API_URL}/document/{filename}")
        response.raise_for_status()
        
        # Re-fetch the list to update the display
        doc_list, selected_doc = get_indexed_documents()
        
        return f"Document **{filename}** deleted successfully.", doc_list, selected_doc
    except requests.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        doc_list, selected_doc = get_indexed_documents()
        return f"Error deleting file: {error_detail}", doc_list, selected_doc
    except Exception as e:
        doc_list, selected_doc = get_indexed_documents()
        return f"An unexpected error occurred during deletion: {e}", doc_list, selected_doc

# 2. Chat Function
def chat_with_api(message, history) -> str:
    """Sends user message and history to the FastAPI chat endpoint."""
    try:
        response = requests.post(
            f"{API_URL}/query", 
            json={"query": message}
        )
        response.raise_for_status()
        return response.json().get("response", "Error: No response from RAG service.")
    except Exception as e:
        return f"An error occurred while querying the RAG API. Is the FastAPI backend running? Details: {e}"

# 3. Gradio Interface Layout
# Get initial state
initial_docs, initial_selected = get_indexed_documents()

# FIX for startup warnings: Ensure initial_selected is a valid choice if documents exist
if initial_docs and not initial_selected:
    initial_selected = initial_docs[0]


with gr.Blocks(title="DocQuery: Chat with your documents") as demo:
    gr.Markdown("# 📜 DocQuery: Chat with your Documents (RAG Demo)")
    
    # Hidden State to track the document list and selected document (needed for chaining)
    doc_list_state = gr.State(value=initial_docs) 
    selected_doc_state = gr.State(value=initial_selected)

    with gr.Row():
        # --- Sidebar for Document Management (Left Column) ---
        with gr.Column(scale=1):
            
            # 1. Document Selector/Deleter Section (TOP)
            gr.Markdown("### 📚 Select Active Document")
            
            # DROPDOWN
            doc_dropdown = gr.Dropdown(
                label="Select Indexed Document to Chat With",
                choices=initial_docs,
                value=initial_selected, # Default selection (now safer)
                interactive=True
            )
            
            # Action buttons for the dropdown
            with gr.Row():
                delete_button = gr.Button("Delete Selected Document 🗑️", variant="stop") 
            
            gr.Markdown("---")
            
            # 2. File Upload Section (BELOW SELECTION, COMPACT)
            gr.Markdown("### ⬆️ Upload New Document")
            
            # FILE UPLOAD (Height maintained)
            file_upload = gr.File(
                label="Upload Document (.pdf, .txt, .docx)", 
                type="filepath", 
                file_types=[".pdf", ".txt", ".docx"],
                height=140
            )
            upload_button = gr.Button("Upload and Index")
            
            # STATUS BOX (Lines maintained)
            upload_output = gr.Textbox(
                label="Indexing Status", 
                value="Ready to index.", 
                interactive=False, 
                lines=3
            )
            
            
            # --- Event Actions ---
            
            # Helper function to update the Dropdown (Uses Gradio 4.x syntax)
            def update_ui_components(d_list, s_doc):
                return [gr.Dropdown(choices=d_list, value=s_doc)]

            # 1. Upload Action
            upload_button.click(
                fn=upload_and_index,
                inputs=[file_upload],
                outputs=[upload_output, doc_list_state, selected_doc_state, file_upload]
            ).then(
                fn=update_ui_components,
                inputs=[doc_list_state, selected_doc_state],
                outputs=[doc_dropdown] 
            )
            
            # 2. SELECTION ACTION (Dropdown Change)
            doc_dropdown.change(
                fn=select_document, 
                # FIX: inputs=[] ensures the selected string value is passed correctly,
                # resolving the "Dropdown object not in choices" error.
                inputs=[], 
                outputs=[upload_output, doc_list_state, selected_doc_state]
            ).then(
                fn=update_ui_components,
                inputs=[doc_list_state, selected_doc_state],
                outputs=[doc_dropdown] 
            )

            # 3. Delete Action
            delete_button.click(
                fn=delete_document,
                inputs=[doc_dropdown], # Must be listed to get the current selected value
                outputs=[upload_output, doc_list_state, selected_doc_state]
            ).then(
                fn=update_ui_components,
                inputs=[doc_list_state, selected_doc_state],
                outputs=[doc_dropdown]
            )
            
        # --- Main Chat Interface (Right Column) ---
        with gr.Column(scale=3):
            gr.Markdown("## 💬 Chat with Indexed Documents")
            gr.ChatInterface(
                fn=chat_with_api,
                title="DocQuery Chat",
            )
            
# Launch the Gradio UI
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)