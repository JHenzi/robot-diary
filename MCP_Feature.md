# **Implement MCP with Chroma for Memories**

* * *

## **1\. Goal**

Enable the LLM to dynamically retrieve relevant past observations (“memories”) during story generation, with the following features:

-   **Hybrid retrieval:** Always include the most recent N temporal memories for continuity (enables morning vs night comparisons), plus top-K semantically relevant memories based on current context.

-   **Vector-based semantic search:** Use embeddings to find contextually similar memories beyond just recency.

-   **Merge and deduplicate:** Combine temporal and semantic results, removing duplicates to minimize input context while maximizing relevance.

-   **Robust fallback:** If MCP/Chroma service is unavailable, preserve at least the recent temporal memories to maintain continuity.

-   **Persistence:** Keep `memories.json` as backup and source-of-truth.

-   **Migration path:** Convert existing JSON memories into Chroma vector store.

-   **Local embedding model:** Avoid external API costs, use lightweight local model (e.g., `sentence-transformers`).
    

* * *

## **2\. Architecture / Deployment Notes**

### **Option A: MCP as Service Adjacent to Existing Docker Container**

-   Run as a **separate container** that exposes a **REST API** for memory queries.
    
-   Pros: Isolation, easier to scale / upgrade independently.
    
-   Cons: Extra container to manage.
    

**Recommended:** For most small projects, running the MCP **inside the existing container** is simpler and avoids inter-container networking complexity.

### **Option B: MCP Inside Existing Container**

-   Add a new Python module (e.g., `mcp.py`) inside your service codebase.
    
-   Provides functions like `query_memories()` callable by the story generation module.
    
-   Handles vector store initialization, query, fallback to JSON.
    

> **Cursor note:** Inspect the codebase to find where story generation is invoked; MCP should be integrated at the point **just before LLM is called**.

* * *

## **3\. Implementation Steps**

### **Step 1: Prepare Chroma vector store**

-   Install Chroma in your container:
    

bash

Copy code

`pip install chromadb sentence-transformers`

-   Initialize Chroma:
    

python

Copy code

`import chromadb from chromadb.config import Settings from sentence_transformers import SentenceTransformer  # Vector DB settings (local, embedded) client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory="./chroma_db"))  collection = client.get_or_create_collection("robot_memories")`

-   Load **local embedding model**:
    

python

Copy code

`embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  # lightweight, local`

* * *

### **Step 2: Migration from existing JSON**

-   Load `memories.json` and convert each summary into an embedding:
    

python

Copy code

`import json  with open("memories.json", "r", encoding="utf-8") as f:     memories = json.load(f)  for mem in memories:     text = mem.get("llm_summary") or mem.get("summary")     emb = embedding_model.encode(text).tolist()     mem["embedding"] = emb     collection.add(         documents=[text],         metadatas={"id": mem["id"], "date": mem["date"]},         ids=[str(mem["id"])],         embeddings=[emb]     )`

-   **Cursor note:** This migration script should **check for duplicates** in Chroma if run multiple times.
    

* * *

### **Step 3: Hybrid memory retrieval function**

-   Create a function that implements hybrid retrieval (temporal + semantic):
    

python

Copy code

`from datetime import datetime, timedelta  def get_hybrid_memories(query_text: str = None, recent_count: int = 5, semantic_top_k: int = 5, context_metadata: dict = None):     """     Hybrid memory retrieval: combines recent temporal memories with semantically relevant ones.     Always includes recent N memories for continuity, plus top-K semantically similar memories.     Merges and deduplicates results.          Args:         query_text: Optional query text for semantic search (e.g., current weather, activity)         recent_count: Number of most recent temporal memories to always include         semantic_top_k: Number of top semantically relevant memories to retrieve         context_metadata: Optional context (date, time, weather) to build query if query_text not provided              Returns:         List of unique memory dictionaries, sorted by date (most recent first)     """     all_memories = []     seen_ids = set()          # Step 1: Always get recent temporal memories (for continuity)     recent_memories = get_recent_temporal_memories(count=recent_count)     for mem in recent_memories:         mem_id = mem.get("id")         if mem_id not in seen_ids:             all_memories.append(mem)             seen_ids.add(mem_id)          # Step 2: Get semantically relevant memories (if Chroma available)     semantic_memories = []     try:         if query_text:             query_emb = embedding_model.encode(query_text).tolist()         elif context_metadata:             # Build query from context (weather, time of day, etc.)             query_text = build_context_query(context_metadata)             query_emb = embedding_model.encode(query_text).tolist()         else:             query_emb = None                  if query_emb:             results = collection.query(                 query_embeddings=[query_emb],                 n_results=semantic_top_k             )                          for doc, meta in zip(results["documents"][0], results["metadatas"][0]):                 mem_id = meta.get("id")                 if mem_id not in seen_ids:  # Deduplicate                     semantic_memories.append({                         "text": doc,                         "id": mem_id,                         "date": meta.get("date"),                         "source": "semantic"  # Track source for debugging                     })                     seen_ids.add(mem_id)     except Exception as e:         logger.warning(f"Semantic search failed: {e}, using temporal memories only")          # Step 3: Merge and deduplicate     all_memories.extend(semantic_memories)          # Sort by date (most recent first)     all_memories.sort(key=lambda m: m.get("date", ""), reverse=True)          return all_memories  def get_recent_temporal_memories(count: int = 5) -> List[Dict]:     """Get most recent N memories from JSON (temporal continuity)."""     with open("memories.json", "r", encoding="utf-8") as f:         memories = json.load(f)     # Sort by date descending     memories.sort(key=lambda m: m.get("date", ""), reverse=True)     return memories[:count]  def build_context_query(context_metadata: dict) -> str:     """Build semantic query from context metadata (weather, time, etc.)."""     parts = []     if context_metadata.get("weather"):         parts.append(f"weather: {context_metadata['weather']}")     if context_metadata.get("time_of_day"):         parts.append(f"time: {context_metadata['time_of_day']}")     return " ".join(parts) if parts else "recent observations"`

* * *

### **Step 4: Fallback logic (built into hybrid retrieval)**

-   The hybrid retrieval function already includes fallback logic:
    

python

Copy code

`def get_hybrid_memories_with_fallback(query_text: str = None, recent_count: int = 5, semantic_top_k: int = 5, context_metadata: dict = None):     """     Hybrid retrieval with guaranteed fallback to temporal memories.     Even if Chroma fails completely, recent temporal memories are always returned.     """     # Always get recent temporal memories first (this never fails if JSON exists)     recent_memories = get_recent_temporal_memories(count=recent_count)          # Try to get semantic memories (may fail silently)     semantic_memories = []     try:         if query_text or context_metadata:             # ... semantic search code from Step 3 ...             pass     except Exception as e:         logger.warning(f"Semantic search unavailable: {e}, using temporal memories only")          # Merge and deduplicate     all_memories = merge_and_deduplicate(recent_memories, semantic_memories)     return all_memories`

-   **LLM prompt injection logic:**
    

python

Copy code

`# Build query from current context (weather, time of day, etc.) context_query = build_context_query(context_metadata)  # Get hybrid memories (always includes recent N, plus semantic matches) relevant_memories = get_hybrid_memories(     query_text=context_query,     recent_count=5,  # Always include 5 most recent for continuity     semantic_top_k=5,  # Plus 5 semantically relevant     context_metadata=context_metadata )  # Format for prompt (use llm_summary if available, else summary) memory_text = format_memories_for_prompt(relevant_memories)  # Inject into LLM prompt prompt = f""" Use the following past observations to enrich the story: {memory_text}  Now generate the story about the latest image and context. """`

* * *

### **Step 5: Update memories after generation**

-   After story generation + summary:
    

python

Copy code

`new_mem = {     "id": next_id,     "date": datetime.utcnow().isoformat(),     "summary": generated_story,     "llm_summary": llm_summary } # Add to JSON memories.append(new_mem) with open("memories.json", "w", encoding="utf-8") as f:     json.dump(memories, f, indent=2)  # Add to Chroma emb = embedding_model.encode(new_mem["llm_summary"]).tolist() collection.add(     documents=[new_mem["llm_summary"]],     metadatas={"id": new_mem["id"], "date": new_mem["date"]},     ids=[str(new_mem["id"])],     embeddings=[emb] )`

* * *

## **6\. Migration Plan**

1.  **Snapshot JSON:** Backup `memories.json`.
    
2.  **Initial migration:** Run script to embed all existing entries into Chroma.
    
3.  **Verify consistency:** Check that hybrid retrieval returns both recent temporal and semantically relevant memories.
    
4.  **Switch memory retrieval:** Replace `get_recent_memory(count=10)` calls with `get_hybrid_memories()` in:
    - `src/service.py` (observation cycle)
    - `src/llm/client.py` (prompt generation)

    (Previously: Replace any “inject recent memories” logic with `query_memories()` calls.
    
5.  **Fallback testing:** Verify that temporal memories are always returned even if Chroma is unavailable.
    
6.  **Ongoing updates:** Each new memory added should update both JSON and Chroma.
    

* * *

## **7\. Cursor Notes / Recommendations**

-   **Inspect codebase** to locate the story generation module; MCP should be invoked **right before LLM call**.
    
-   **Docker integration:** If inside existing container, update `requirements.txt` with `chromadb` and `sentence-transformers`.
    
-   **Resource consideration:** Local embedding model should fit within container CPU/memory limits.
    
-   **Scalability:** For tens of thousands of memories, Chroma + embeddings will scale well.
    
-   **Testing:** Implement unit tests for:
    
    -   Query results match expected top-N
        
    -   Fallback works if Chroma unavailable
        
    -   JSON backup is consistent with Chroma store
        

* * *

This setup gives you:

-   **Hybrid memory retrieval:** Combines temporal continuity (recent N memories) with semantic relevance (top-K matches).
    
-   **Minimized input context:** Deduplication ensures only unique, relevant memories are passed to the LLM.
    
-   **Robust fallback:** Recent temporal memories are always preserved even if Chroma/MCP is unavailable, maintaining continuity for morning vs night comparisons.
    
-   **Lightweight local embeddings** to keep costs low.
    
-   **Incremental migration** from existing JSON data.

