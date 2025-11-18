# langgraph
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any, Optional

from .vector_store import (
    DEFAULT_INDEX,
    embed_query,
    retrieve_topk,
 )

from .llm import generate_with_hf


# Global Checkpointer Singleton (Only instantiate once)
from langgraph.checkpoint.memory import MemorySaver
CHECKPOINTER = MemorySaver()

class StateDict(TypedDict):
    """
    Represents the state of the RAG pipeline.
    This replaces the simple 'class StateDict(dict):'
    """
    # Required Inputs
    query: str
    index_name: str
    top_k: int
    
    # Generated Intermediate Variables
    query_embedding: List[float]
    retrieved: List[Dict[str, Any]] # List of {"text", "metadata", "score"}
    
    # Final Output
    answer: str
    
    # Error Handling
    error: Optional[str] # Use Optional since it might be missing

    history: List[Dict[str, str]]

def _node_load_query(state: StateDict) -> StateDict:
    print("_node_load_query")
    q = state.get("query")
    if not q or not isinstance(q, str) or not q.strip():
        state["error"] = "empty query"
        return state
    state["query"] = q.strip()
    state["index_name"] = state.get("index_name") or DEFAULT_INDEX
    state["top_k"] = int(state.get("top_k", 4))
    # print("state ->\n ", state)
    return state

def _node_embed_query(state: StateDict) -> StateDict:
    print("_node_embed_query")
    if state.get("error"):
        return state
    q = state.get("query", "")
    try:
        state["query_embedding"] = embed_query(q)
        # print("state ->\n ", "query_embedding")
    except Exception as e:
        state["error"] = f"embed error: {e}"
        
    return state

def _node_retrieve(state: StateDict) -> StateDict:
    print("_node_retrieve")
    if state.get("error"):
        return state
    idx = state.get("index_name", DEFAULT_INDEX)
    top_k = int(state.get("top_k", 4))
    try:
        state["retrieved"] = retrieve_topk(idx, state["query"], top_k=top_k)
        # print("state ->\n ", state)
    except Exception as e:
        state["error"] = f"retrieve error: {e}"
    return state

def _node_generate(state: StateDict) -> StateDict:
    """
    Generate answer using HF LLM.
    Implements a persistent sliding window of last 5 Q/A for context.
    Stores only serializable data in state.
    """
    if state.get("error"):
        return state

    query = state.get("query") or state.get("question") or ""
    index_name = state.get("index_name") or DEFAULT_INDEX

    # --- 1) Retrieve last 5 Q/A from memory ---
    # Load last memory
    
    memory = state.get("history", [])
    memory = memory[-5:] # keep only last 5
    
    # PRINT THE HISTORY to debug
    print(f"Current history length: {len(memory)}") 
    if memory:
        print(f"Last Q/A: Q: {memory[-1]['question'][:30]}... A: {memory[-1]['answer'][:30]}...")


    # --- 2) Build context from retrieval hits ---
    retrieved = state.get("retrieved", []) or []
    pieces = []
    for i, hit in enumerate(retrieved):
        meta = hit.get("metadata") or {}
        src = meta.get("source") or meta.get("file") or f"chunk_{i}"
        pieces.append(f"Source: {src}\n\n{hit.get('text','')}")
    context = "\n\n---\n\n".join(pieces)

    # --- 3) Build system prompt with memory ---
    memory_prompt = ""
    if memory:
        memory_texts = [f"Q: {m['question']}\nA: {m['answer']}" for m in memory]
        memory_prompt = "\n\n Last questions asked are :\n" + "\n".join(memory_texts)

    sys_prompt = f"""You are DocQuery, a helpful document assistant.
Use ONLY the context below to answer the question. 
If the answer cannot be found in the context, respond with "I don't know".

Instructions:
- Use the provided context to answer the question.
- Include relevant previous session Q/A if needed.
- Provide direct answer only, no hallucinations.

* Whenever user asks about last question, you can use below below memory context to anser.
{memory_prompt}

Context:
{context}

Answer:"""
    # --- 4) Generate answer ---
    resp = generate_with_hf(sys_prompt, prompt=query)
    state["answer"] = resp
    if resp:
            mem_entry = {"question": query, "answer": resp} # index_name is saved by LangGraph checkpoint
            current_history = state.get("history", [])
            current_history.append(mem_entry)
            state["history"] = current_history
            print("Memory is updated/Inserted")

    print(f"State updated with history length: {len(state.get('history', []))}")

    return state

def get_rag_graph():
    """
    Build and return compiled LangGraph runnable graph.
    """
    graph = StateGraph(StateDict)
    graph.add_node("load_query", _node_load_query)
    graph.add_node("embed_query", _node_embed_query)
    graph.add_node("retrieve", _node_retrieve)
    graph.add_node("generate", _node_generate)

    graph.add_edge(START, "load_query")
    graph.add_edge("load_query", "embed_query")
    graph.add_edge("embed_query", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    # Persistent memory
    compiled = graph.compile(checkpointer=CHECKPOINTER)

    return compiled


def answer_query_with_graph(question: str, index_name: str, top_k: int = 4, return_intermediate_steps: bool = False) -> Dict[str, Any]:
    """
    Execute the RAG graph using a question and index_name.
    - Uses persistent memory (MemorySaver) to store last 5 Q/A per thread.
    - Feeds last 5 Q/A to LLM as context.
    - Returns structured dict with answer and retrieved docs.
    """
    from langgraph.checkpoint.memory import MemorySaver

    # Graph expects "query", not "question"
    state = {
        "query": question,
        "index_name": index_name,
        "top_k": top_k
    }

    graph = get_rag_graph()
    
    res = graph.invoke(
        state,
        return_intermediate_steps=return_intermediate_steps,
        config={
            "configurable": {
                "thread_id": index_name,       # memory thread
                "checkpoint_ns": "rag_memory", # memory namespace
            }
        }
    )
    return res