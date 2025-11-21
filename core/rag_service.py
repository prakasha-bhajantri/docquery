import os
import chromadb
from llama_index.core import (
    Settings,
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.nvidia import NVIDIA
from llama_index.embeddings.nvidia import NVIDIAEmbedding
from llama_index.postprocessor.flashrank_rerank import FlashRankRerank
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine import ContextChatEngine
from llama_index.core.chat_engine.types import BaseChatEngine
from typing import List
from dotenv import load_dotenv

# Load environment variables (CRITICAL: Must be run before initializing NVIDIA classes)
load_dotenv() 

# --- CONFIGURATION ---
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "my_rag_collection"
TEMP_UPLOAD_DIR = "./temp_uploads"

# --- LLM Settings ---
MODEL_LLM = os.getenv("MODEL_LLM")
MODEL_EMBEDDINGS = os.getenv("MODEL_EMBEDDINGS")

# CRITICAL: The NVIDIA connectors automatically use the NVIDIA_API_KEY from os.environ
Settings.embed_model = NVIDIAEmbedding(model_name=MODEL_EMBEDDINGS)

Settings.llm = NVIDIA(
    model=MODEL_LLM,
    max_tokens=256,
    temperature=0.0,
    stop_sequences=["\n\n", "</s>", "<|eot_id|>", "Answer:", "Thank you", "Here is"],
)
SYSTEM_PROMPT = (
    "You are a strict document assistant. "
    "Your goal is to provide **only** factual answers based **strictly** on the context provided. "
    "DO NOT add any introductory phrases, conversational fillers, or polite sign-offs. "
    "If the answer is not in the context, say 'I do not know' and nothing else."
    "Always maintain a concise and factual tone."
    "When some one says hi/greetings, just greet them nicely with Hi and say what do you want to know from yur document"
)

class RAGService:
    def __init__(self):
        # 1. Initialize Chroma Client and Vector Store
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.chroma_collection = self.chroma_client.get_or_create_collection(COLLECTION_NAME)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # 2. Load or Create Index
        try:
            # Attempt to load the index from the existing vector store
            self.index = VectorStoreIndex.from_vector_store(self.vector_store, storage_context=self.storage_context)
        except Exception:
            # Create an empty index if the collection is new or empty
            self.index = VectorStoreIndex([], storage_context=self.storage_context)
        
        # 3. Setup Reranker and Chat Engine
        self.local_reranker = FlashRankRerank(model_name="bge-reranker-base", top_n=3)
        self.chat_engine: BaseChatEngine = self._create_chat_engine()

        # 4. Track selected file and set default
        self.selected_document: str = ""
        doc_list = self.get_document_list()
        if doc_list:
            self.selected_document = doc_list[0]

    def _create_chat_engine(self) -> ContextChatEngine:
        """Initializes/Re-initializes the ContextChatEngine."""

        retriever = self.index.as_retriever(similarity_top_k=5)
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        
        return ContextChatEngine.from_defaults(
            retriever=retriever,
            node_postprocessors=[self.local_reranker],
            memory=memory,
            system_prompt=SYSTEM_PROMPT,
        )

    def get_document_list(self) -> List[str]:
        """Fetches list of unique filenames from Chroma metadata."""
        doc_names = set()
        
        # Query Chroma for all metadata (up to 100k items)
        results = self.chroma_collection.get(limit=100000, include=['metadatas'])
        
        for metadata in results.get('metadatas', []):
            # Use the reliable 'file_name' key we set during upload
            if 'file_name' in metadata:
                doc_names.add(metadata['file_name'])
            # Fallback for documents indexed before the fix
            elif 'file_path' in metadata:
                 doc_names.add(os.path.basename(metadata['file_path']))
        
        return sorted(list(doc_names))


    async def upload_and_index_document(self, file_path: str):
        """Loads, chunks, adds custom metadata, and indexes a new document."""
        new_filename = os.path.basename(file_path)
        
        # 1. Load the single document
        reader = SimpleDirectoryReader(input_files=[file_path])
        docs = reader.load_data()

        # 2. Add custom metadata for reliable deletion/listing
        for doc in docs:
            doc.metadata['file_name'] = new_filename 

        # 3. Create Chunks --> Nodes
        node_parser = SentenceSplitter(chunk_size=300, chunk_overlap=30)
        nodes = node_parser.get_nodes_from_documents(docs, show_progress=False)

        # 4. Insert nodes into the existing index
        self.index.insert_nodes(nodes)

        # 5. Update state and clean up
        self.chat_engine = self._create_chat_engine()
        self.selected_document = new_filename # Set newly uploaded file as selected
        os.remove(file_path)
        
        return {"filename": new_filename, "status": "Indexed and ready"}

    def set_selected_document(self, filename: str):
        """Sets the currently active document for QA."""
        if filename in self.get_document_list():
            self.selected_document = filename
            self.chat_engine = self._create_chat_engine()
            return True
        return False
        
    async def delete_document(self, filename: str):
        """Deletes all nodes belonging to a specific document from Chroma."""
        collection = self.chroma_collection
        
        try:
            # 1. Query Chroma using the reliable 'file_name' metadata key
            results = collection.get(
                where={"file_name": filename},
                include=[] # No need to include metadata/documents for deletion
            )
            
            ids_to_delete = results.get('ids', [])

            if not ids_to_delete:
                return False, f"File {filename} not found in index."
            
            # 2. Delete the chunks (nodes)
            collection.delete(ids=ids_to_delete)
            
            # 3. Update selected document tracking
            if self.selected_document == filename:
                self.selected_document = ""
                doc_list = self.get_document_list()
                if doc_list:
                    self.selected_document = doc_list[0] # Select the first available doc

            # Re-initialize the chat engine after deletion
            self.chat_engine = self._create_chat_engine()
            
            return True, f"File {filename} deleted and index updated."

        except Exception as e:
            print(f"Error during document deletion: {e}")
            return False, f"Failed to delete {filename}: {e}"
        
    async def chat_query(self, query: str):
        """Submits a query to the chat engine."""
        # Use the asynchronous chat method
        response = await self.chat_engine.achat(query)
        return response.response

# Global service instance (Initialized only once at startup)
rag_service = RAGService()