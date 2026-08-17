import streamlit as st
import os
import time
import json
from typing import Dict, Any

# Import local pipeline engines
from rag_pipeline import PersistentRAGVectorStore, RAGLLM, KNOWLEDGE_BASE_DIR, INDEX_DIR

# Page configuration
st.set_page_config(
    page_title="FreightQuote AI - RAG Knowledge Center",
    page_icon="📖",
    layout="wide"
)

# Custom Styling
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #0f172a 0%, #020617 100%);
        color: #f8fafc;
    }
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
    }
    .chunk-card {
        background-color: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-badge {
        display: inline-block;
        background-color: #1e293b;
        color: #38bdf8;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 8px;
    }
    .stTextInput>div>div>input {
        background-color: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
    }
    .stButton>button {
        background: linear-gradient(90deg, #0284c7 0%, #0369a1 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #0ea5e9 0%, #0284c7 100%);
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# Cache Loaders
@st.cache_resource
def load_rag_systems():
    """Initializes and caches Vector Store and LLM for Streamlit UI."""
    vector_store = PersistentRAGVectorStore()
    
    # Load index from disk
    if os.path.exists(INDEX_DIR):
        print("[Streamlit App] Loading persistent FAISS index from disk...")
        vector_store.load_index(INDEX_DIR)
    else:
        print("[Streamlit App] WARNING: FAISS index folder not found. Run pipeline first.")
        
    llm = RAGLLM()
    # Attempt to load LLM (Qwen in 4-bit on GPU, or rule fallback)
    llm.load_llm()
    
    return vector_store, llm

# Initialize systems
vector_store, llm = load_rag_systems()

st.title("📖 FreightQuote AI - RAG Knowledge Center")
st.markdown("<p style='color: #94a3b8;'>Semantic Search & Intelligent QA over Logistics SOPs, Policies, and Customs Guidelines</p>", unsafe_allow_html=True)

# Sidebar metrics
st.sidebar.markdown("### 📊 System Status")
if llm.gpu_available and llm.model is not None:
    st.sidebar.success("🟢 GPU Mode: Qwen2.5-3B Quantized")
else:
    st.sidebar.info("🔵 Fallback Mode: CPU Rules Heuristic")
    
# Display dataset metrics if files exist
if os.path.exists(INDEX_DIR) and vector_store.index is not None:
    st.sidebar.markdown(f"**Index size**: `{vector_store.index.ntotal}` text chunks")
    
# Show counts of PDFs in directory
if os.path.exists(KNOWLEDGE_BASE_DIR):
    pdf_files = [f for f in os.listdir(KNOWLEDGE_BASE_DIR) if f.lower().endswith('.pdf')]
    st.sidebar.markdown(f"**Indexed documents**: `{len(pdf_files)}` PDFs")
else:
    st.sidebar.markdown("**Indexed documents**: `0` PDFs")

# MAIN CHAT/QUERY INTERFACE
query = st.text_input("Enter your logistics question:", placeholder="e.g., What is the detention charge after 2 hours?")

if st.button("Search Knowledge Base") or query:
    if not query.strip():
        st.warning("Please enter a question.")
    elif vector_store.index is None:
        st.error("Error: FAISS vector database is not loaded. Please build the index in the notebook.")
    else:
        with st.spinner("Searching documents & generating answer..."):
            # 1. Retrieval
            retrieval_start = time.time()
            hits = vector_store.search(query, top_k=4)
            retrieval_latency = time.time() - retrieval_start
            
            # 2. Answer generation
            answer_start = time.time()
            answer, gen_latency = llm.generate_answer(query, hits)
            
            # 3. Output
            st.markdown("### 🤖 Answer")
            st.info(answer)
            
            # Metadata badges
            st.markdown(
                f"<span class='metric-badge'>Retrieval Latency: {retrieval_latency:.4f}s</span>"
                f"<span class='metric-badge'>Generation Latency: {gen_latency:.4f}s</span>"
                f"<span class='metric-badge'>Total Chunks Searched: {len(hits)}</span>",
                unsafe_allow_html=True
            )
            
            # 4. Retrieved Chunks
            st.markdown("### 📄 Retrieved Context Chunks")
            for idx, hit in enumerate(hits):
                score = hit["score"]
                source = hit["metadata"]["source"]
                page = hit["metadata"]["page"]
                content = hit["metadata"]["content"]
                
                # Format chunk card
                st.markdown(f"""
                <div class="chunk-card">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-weight: bold; color: #38bdf8;">[Chunk {idx+1}] Source: {source} (Page {page})</span>
                        <span style="color: #22c55e; font-weight: bold;">Score: {score:.4f}</span>
                    </div>
                    <div style="font-size: 13px; color: #cbd5e1; line-height: 1.5;">
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
# Clear Chat / Reset memory
if st.sidebar.button("Clear Conversation Memory"):
    llm.memory = []
    st.sidebar.success("Memory cleared.")
