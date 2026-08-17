import os
import time
import json
import random
import torch
import shutil
from typing import List, Dict, Tuple, Any, Optional

# reportlab for generating mock PDFs
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# pypdf for loading PDFs
from pypdf import PdfReader

# langchain splitters
from langchain.text_splitter import RecursiveCharacterTextSplitter

# sentence-transformers
from sentence_transformers import SentenceTransformer

# FAISS
import faiss
import numpy as np

# HuggingFace for LLM
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# Set random seed
random.seed(42)

# Global configuration
KNOWLEDGE_BASE_DIR = "KnowledgeBase"
INDEX_DIR = "faiss_index"

# ----------------- KNOWLEDGE BASE GENERATOR -----------------

def create_mock_pdf(filepath: str, title: str, paragraphs: List[str]):
    """Generates a multi-page PDF with line-wrapped paragraphs using reportlab."""
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(54, height - 54, title)
    
    y = height - 90
    c.setFont("Helvetica", 10)
    
    for p_idx, para in enumerate(paragraphs):
        # Draw paragraph index as subheader
        c.setFont("Helvetica-Bold", 11)
        c.drawString(54, y, f"Section {p_idx+1}")
        y -= 15
        c.setFont("Helvetica", 10)
        
        words = para.split()
        line = ""
        for word in words:
            if c.stringWidth(line + " " + word, "Helvetica", 10) < (width - 108): # margins 54 on both sides
                line += " " + word
            else:
                c.drawString(54, y, line.strip())
                y -= 14
                line = word
                if y < 54:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 54
        if line:
            c.drawString(54, y, line.strip())
            y -= 25 # space between sections
            
        if y < 80:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 54
            
    c.save()

def generate_knowledge_base(output_dir: str = KNOWLEDGE_BASE_DIR, count: int = 50):
    """Generates 50+ unique logistics PDFs + 2 corrupted files for pipeline test validation."""
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    topics = [
        ("Customs_Compliance_Guide", [
            "Customs clearance requires submission of Form US-382 and commercial invoices detailing HTS code classifications. Incorrect codes lead to audit penalties.",
            "International shipping transit zones require custom clearance manifests filed 48 hours prior to port arrival. Late declarations carry a tariff penalty of $500 per day.",
            "Bonded warehouses provide storage under customs authority. All cargo stored in Zone-B must satisfy security requirements under Customs Rule 409.",
            "Hazardous materials (HAZMAT) require class-specific documentation and packaging compliance. Violations lead to immediate suspension of shipping licenses."
        ]),
        ("Route_Optimization_Protocol", [
            "Route efficiency is computed using weather parameters, traffic densities, and road toll metrics. Zone 3 corridors carry a default delay of 45 minutes during peak hours.",
            "Winter routing strategies dictate diversion paths when snowfall exceeds 3 inches per hour. Alternate highway corridor Route 90 is designated for heavy carriage.",
            "Port congestion at Port of Long Beach requires carrier scheduling windows to avoid delays. Standard dwell time of containers averages 4.2 days.",
            "Last mile delivery optimization targets regional depots. Vehicles exceeding 12,000 lbs are restricted from urban residential deliveries under city laws."
        ]),
        ("Carrier_Safety_Standard", [
            "Carrier compliance mandates safety audits every 6 months. Minimum passing FMCSA safety rating is 85 percent, beneath which carriers face suspension.",
            "Insurance liabilities require minimum coverage of 2 million dollars for active line-haul carriers. Verified documents must be renewed yearly.",
            "Carrier compliance metrics log driver rest times under ELD rules. Violations of hours-of-service carry a safety score reduction of 5 points.",
            "Maintenance logs must verify tire pressure checks and brake inspections. Under-inflated tires decrease fuel efficiency by 3.4 percent."
        ]),
        ("Pricing_and_Surcharges", [
            "Fuel surcharges are indexed weekly against the national diesel average. Base rate triggers surcharge additions when diesel exceeds $3.50 per gallon.",
            "Peak season surcharges apply from October 1 to December 24, adding 15 percent to flatbed and dry van line-haul rates across North American routes.",
            "Less-Than-Truckload (LTL) pricing uses NMFC freight classes. Freight classes are determined by density, stowability, handling, and liability risk.",
            "Accessorial fees include liftgate service, detention charges ($75 per hour after 2 hours), inside delivery, and residential pickup surcharges."
        ]),
        ("Logistics_Insurance_Policy", [
            "Cargo insurance coverage is limited to $100,000 standard liability unless declared value additions are requested during initial booking confirmation.",
            "Claims for damaged freight must be submitted within 9 days of delivery receipt, accompanied by photographic evidence and bill of lading annotations.",
            "Act of God clauses exclude coverage during extreme category 4+ weather events. Alternative routing safety procedures must be documented.",
            "Reefer cargo temperature deviations exceeding 4 degrees Fahrenheit for more than 2 hours void standard compliance safety profiles."
        ])
    ]
    
    # Generate 50 clean PDFs
    for idx in range(1, count + 1):
        topic_name, paragraphs = topics[(idx - 1) % len(topics)]
        # Add random variations to paragraphs to make documents unique
        unique_paras = []
        for p in paragraphs:
            unique_paras.append(p + f" Document reference code: FREIGHT-ID-{idx:03d}-{random.randint(1000, 9999)}.")
            
        filename = f"{topic_name}_Part{idx}.pdf"
        filepath = os.path.join(output_dir, filename)
        create_mock_pdf(filepath, f"Logistics Standard Operating Procedure - Ref {idx:03d}", unique_paras)
        
    # Generate 2 corrupted PDFs
    with open(os.path.join(output_dir, "Corrupt_Customs_Declaration.pdf"), "w") as f:
        f.write("This is a corrupted text file pretending to be a PDF header.")
        
    with open(os.path.join(output_dir, "Blank_Document_Error.pdf"), "wb") as f:
        f.write(b"%PDF-1.4\n%EOF") # minimum header but empty structure to cause parse failure
        
    print(f"Generated {count} clean logistics PDFs and 2 corrupted files in folder: {output_dir}")

# ----------------- INGESTION PIPELINE -----------------

class RAGIngestionPipeline:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 60):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        
    def load_and_chunk_documents(self, folder: str = KNOWLEDGE_BASE_DIR) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Scans folder, loads non-corrupted PDFs, chunks text, and returns document metrics."""
        start_time = time.time()
        documents = []
        pdf_count = 0
        corrupted_count = 0
        total_pages = 0
        
        pdf_files = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
        
        for file in pdf_files:
            filepath = os.path.join(folder, file)
            try:
                reader = PdfReader(filepath)
                pages = reader.pages
                page_count = len(pages)
                
                # Check for corrupted or empty pages
                if page_count == 0:
                    raise ValueError("Empty PDF")
                    
                text_content = ""
                for idx, page in enumerate(pages):
                    page_text = page.extract_text() or ""
                    text_content += page_text + "\n"
                    # Add individual chunk info if needed, but we chunk globally
                    
                if not text_content.strip():
                    raise ValueError("No extractable text content")
                    
                pdf_count += 1
                total_pages += page_count
                
                # Chunk document
                chunks = self.text_splitter.split_text(text_content)
                for chunk_idx, chunk in enumerate(chunks):
                    documents.append({
                        "content": chunk,
                        "metadata": {
                            "source": file,
                            "page": (chunk_idx // 2) + 1, # approximation of page offset
                            "doc_index": pdf_count
                        }
                    })
            except Exception as e:
                # Log corrupted file and skip
                corrupted_count += 1
                print(f"[LOAD ERROR] Skipping corrupted PDF '{file}': {e}")
                
        metrics = {
            "total_pdfs": pdf_count,
            "corrupted_pdfs": corrupted_count,
            "total_pages": total_pages,
            "total_chunks": len(documents),
            "ingestion_latency_seconds": time.time() - start_time
        }
        return documents, metrics

# ----------------- VECTOR STORE -----------------

class RAGVectorStore:
    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(embedding_model_name)
        self.index = None
        self.doc_metadata: List[Dict[str, Any]] = []
        
    def build_index(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Encodes document chunks, creates FAISS index, and saves metadata."""
        start_time = time.time()
        texts = [doc["content"] for doc in documents]
        self.doc_metadata = [doc["metadata"] for doc in documents]
        
        # Embedding text
        embeddings = self.model.encode(texts, show_progress_bar=False)
        embedding_time = time.time() - start_time
        
        # FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension) # Inner product (Cosine similarity if normalized)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        db_time = time.time() - (start_time + embedding_time)
        
        metrics = {
            "embedding_time_seconds": embedding_time,
            "vector_db_creation_time_seconds": db_time,
            "total_indexed_chunks": self.index.ntotal
        }
        return metrics
        
    def save_index(self, folder: str = INDEX_DIR):
        """Persists the FAISS index and metadata to disk."""
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        faiss.write_index(self.index, os.path.join(folder, "index.faiss"))
        with open(os.path.join(folder, "metadata.json"), "w") as f:
            json.dump(self.doc_metadata, f, indent=4)
            
    def load_index(self, folder: str = INDEX_DIR) -> bool:
        """Loads FAISS index and metadata from disk if exists."""
        index_path = os.path.join(folder, "index.faiss")
        meta_path = os.path.join(folder, "metadata.json")
        if not (os.path.exists(index_path) and os.path.exists(meta_path)):
            return False
            
        self.index = faiss.read_index(index_path)
        with open(meta_path, "r") as f:
            self.doc_metadata = json.load(f)
        return True
        
    def search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Queries the vector index and returns similarity matches."""
        query_vector = self.model.encode([query])
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.doc_metadata):
                continue
            # Get original document text chunk
            # To fetch original chunk text, we either need to persist it or read from cache.
            # In our case, we will store chunk contents in metadata or keep in memory.
            # Let's write contents directly in the saved index metadata or reload
            # For simplicity, we keep original texts in memory. We'll store it inside the search context.
            results.append({
                "score": float(score),
                "metadata": self.doc_metadata[idx]
            })
        return results

# Let's subclass Vector Store to include chunk text in metadata when saving to disk
class PersistentRAGVectorStore(RAGVectorStore):
    def build_index(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        start_time = time.time()
        texts = [doc["content"] for doc in documents]
        
        # Embed
        embeddings = self.model.encode(texts, show_progress_bar=False)
        embedding_time = time.time() - start_time
        
        # Build index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        # Keep chunk text in metadata
        self.doc_metadata = []
        for doc in documents:
            meta = doc["metadata"].copy()
            meta["content"] = doc["content"]
            self.doc_metadata.append(meta)
            
        db_time = time.time() - (start_time + embedding_time)
        return {
            "embedding_time_seconds": embedding_time,
            "vector_db_creation_time_seconds": db_time,
            "total_indexed_chunks": self.index.ntotal
        }

# ----------------- LLM PIPELINE -----------------

class RAGLLM:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.gpu_available = torch.cuda.is_available()
        self.memory: List[Dict[str, str]] = [] # Simple conversational memory
        
    def load_llm(self) -> bool:
        """Loads Qwen2.5-3B-Instruct in 4-bit mode on GPU."""
        model_id = "Qwen/Qwen2.5-3B-Instruct"
        if not self.gpu_available:
            print("[RAGLLM] GPU not detected. Using CPU rule-based generation fallback.")
            return False
            
        try:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            print("[RAGLLM] Quantized 4-bit model loaded successfully on GPU.")
            return True
        except Exception as e:
            print(f"[RAGLLM] GPU loading failed: {e}. Falling back to CPU mode.")
            return False
            
    def generate_answer(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[str, float]:
        """Generates answer using retrieved contexts and conversation memory."""
        start_time = time.time()
        
        # Build prompt context
        context_str = ""
        for idx, chunk in enumerate(retrieved_chunks):
            context_str += f"[Source {idx+1}: {chunk['metadata']['source']} (Page {chunk['metadata']['page']})]\n{chunk['metadata']['content']}\n\n"
            
        # Conversation history
        history_str = ""
        for turn in self.memory[-3:]: # last 3 turns
            history_str += f"User: {turn['query']}\nAI: {turn['answer']}\n"
            
        system_prompt = (
            "You are the FreightQuote AI Assistant. Answer the user's question using ONLY the provided document contexts. "
            "If the answer cannot be found in the context, say: 'I cannot find the answer in the provided documents.' "
            "Do not make up facts or use external knowledge."
        )
        
        prompt = f"""
        Document Contexts:
        {context_str}
        
        Conversation History:
        {history_str}
        
        Question: {query}
        
        Provide a concise, direct answer based strictly on the contexts. Cite the Source files and Page numbers in your response.
        """
        
        latency = 0.0
        answer = ""
        
        if self.model is not None and self.tokenizer is not None:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
                text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                model_inputs = self.tokenizer([text], return_tensors="pt").to("cuda")
                
                with torch.no_grad():
                    generated_ids = self.model.generate(
                        **model_inputs,
                        max_new_tokens=256,
                        temperature=0.2
                    )
                generated_ids = [
                    output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                ]
                answer = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
                latency = time.time() - start_time
            except Exception as e:
                print(f"[RAGLLM] GPU inference failed: {e}. Executing CPU fallback generator.")
                self.model = None # Force fallback
                
        if self.model is None:
            # High quality CPU fallback generator
            # Scans retrieved chunks for keyword matches and returns structured response
            answer = self.fallback_rule_based_qa(query, retrieved_chunks)
            latency = time.time() - start_time
            
        # Update memory
        self.memory.append({"query": query, "answer": answer})
        return answer, latency

    def fallback_rule_based_qa(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Heuristic question answering engine for CPU fallback."""
        if not chunks:
            return "I cannot find the answer in the provided documents."
            
        # Simple keywords search in chunks
        query_words = [w.lower() for w in query.replace("?", "").split() if len(w) > 3]
        best_chunk = chunks[0] # Default to top matching chunk
        max_overlap = 0
        
        for chunk in chunks:
            content_lower = chunk['metadata']['content'].lower()
            overlap = sum(1 for w in query_words if w in content_lower)
            if overlap > max_overlap:
                max_overlap = overlap
                best_chunk = chunk
                
        source = best_chunk['metadata']['source']
        page = best_chunk['metadata']['page']
        content = best_chunk['metadata']['content']
        
        # Generate clean summary answer
        # Find sentence containing matching keywords
        sentences = content.split(".")
        relevant_sentences = []
        for sent in sentences:
            if any(w in sent.lower() for w in query_words):
                relevant_sentences.append(sent.strip())
                
        if relevant_sentences:
            extracted = ". ".join(relevant_sentences[:2]) + "."
        else:
            extracted = content.strip().split("\n")[0] # first line
            
        return f"{extracted} [Source: {source}, Page: {page}]"
