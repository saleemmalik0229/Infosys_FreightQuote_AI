import time
import pandas as pd
from typing import List, Dict, Any
from rag_pipeline import PersistentRAGVectorStore, RAGLLM

def get_eval_questions() -> List[str]:
    """Returns a list of 32 logistics questions covering all core categories."""
    return [
        # Customs Compliance (1-6)
        "What forms are required for customs clearance?",
        "What is the penalty for late custom clearance declarations?",
        "Under what rule must Zone-B cargo satisfy customs security?",
        "What happens if HAZMAT packaging violates compliance regulations?",
        "What is the filing window for custom clearance manifests?",
        "HTS code classification is required on what documents?",
        
        # Route Optimization (7-12)
        "How is routing efficiency computed?",
        "What corridor carries a 45 minute peak hour delay?",
        "Which highway is the alternate corridor for winter heavy carriage?",
        "What is the average dwell time at Port of Long Beach?",
        "What vehicle weight is restricted from residential delivery?",
        "When does snowfall trigger routing diversions?",
        
        # Carrier Safety & Compliance (13-18)
        "How often must carrier safety audits be conducted?",
        "What is the minimum passing score for FMCSA safety rating?",
        "What is the required insurance coverage limit for active line-haul carriers?",
        "How many safety score points are deducted for driver hours-of-service violations?",
        "By what percentage does under-inflated tire pressure decrease fuel efficiency?",
        "What logs must verify maintenance status?",
        
        # Pricing & Surcharges (19-25)
        "How are fuel surcharges indexed?",
        "When do peak season surcharges apply?",
        "What parameters determine LTL freight pricing?",
        "What is the hourly rate for carrier detention after 2 hours?",
        "When does diesel fuel trigger additional fuel surcharges?",
        "What accessorial fees are charged by carriers?",
        "What percentage is added for flatbed peak season line-haul rates?",
        
        # Cargo Insurance (26-32)
        "What is the standard liability insurance limit for cargo?",
        "Within how many days must freight damage claims be submitted?",
        "Are category 4 storm events covered under standard clauses?",
        "What reefer temperature deviations void compliance safety?",
        "What documents must accompany photographic evidence for cargo claims?",
        "Does standard insurance cover Acts of God?",
        "How many hours of temperature deviation will void reefer compliance?"
    ]

def run_evaluation(vector_store: PersistentRAGVectorStore, llm: RAGLLM) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Runs the 32 queries evaluation suite, tracks latency, retrieval accuracy, and compiles summary."""
    questions = get_eval_questions()
    results = []
    
    total_latency = 0.0
    total_retrieval_latency = 0.0
    passed_queries = 0
    
    print(f"Starting automated evaluation of {len(questions)} logistics queries...")
    
    for idx, query in enumerate(questions):
        # 1. Retrieval
        retrieval_start = time.time()
        hits = vector_store.search(query, top_k=3)
        ret_latency = time.time() - retrieval_start
        total_retrieval_latency += ret_latency
        
        # 2. Answer generation
        ans_start = time.time()
        answer, gen_latency = llm.generate_answer(query, hits)
        ans_latency = time.time() - ans_start
        total_latency += ans_latency
        
        # 3. Validation / Grading
        # Pass criteria: Retrieval successfully returned at least 1 document and score > 0.3
        top_score = hits[0]["score"] if hits else 0.0
        status = "Pass" if (hits and top_score > 0.25 and "cannot find the answer" not in answer.lower()) else "Fail"
        if status == "Pass":
            passed_queries += 1
            
        retrieved_doc = hits[0]["metadata"]["source"] if hits else "None"
        retrieved_page = hits[0]["metadata"]["page"] if hits else "None"
        
        results.append({
            "Query ID": f"Q-{idx+1:02d}",
            "Question": query,
            "Retrieved Source": retrieved_doc,
            "Page": retrieved_page,
            "Similarity Score": f"{top_score:.4f}",
            "Answer": answer[:120] + ("..." if len(answer) > 120 else ""),
            "Status": status,
            "Latency (s)": f"{ans_latency:.3f}"
        })
        
        print(f"[{idx+1}/{len(questions)}] Query ID: Q-{idx+1:02d} | Status: {status} | Latency: {ans_latency:.2f}s")
        
    df = pd.DataFrame(results)
    
    # Calculate averages
    avg_gen_latency = total_latency / len(questions)
    avg_ret_latency = total_retrieval_latency / len(questions)
    
    summary = {
        "passed_queries": passed_queries,
        "total_queries": len(questions),
        "average_generation_latency": avg_gen_latency,
        "average_retrieval_latency": avg_ret_latency,
        "pass_rate_percent": (passed_queries / len(questions)) * 100
    }
    
    return df, summary
