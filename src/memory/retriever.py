"""Hybrid memory retrieval using ChromaDB for semantic search and temporal continuity."""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime

try:
    import chromadb
    try:
        from chromadb.config import Settings  # Old API
    except ImportError:
        Settings = None  # New API doesn't need Settings
    from sentence_transformers import SentenceTransformer
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    Settings = None
    logging.warning("ChromaDB or sentence-transformers not available. Semantic search will be disabled.")

from ..config import MEMORY_DIR

logger = logging.getLogger(__name__)

MEMORY_FILE = MEMORY_DIR / 'observations.json'
CHROMA_DB_PATH = MEMORY_DIR / 'chroma_db'
COLLECTION_NAME = "robot_memories"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # Lightweight, local embedding model


class HybridMemoryRetriever:
    """
    Hybrid memory retrieval that combines:
    1. Recent temporal memories (for continuity, morning vs night comparisons)
    2. Semantically relevant memories (based on current context)
    
    Always falls back to temporal memories if ChromaDB is unavailable.
    """
    
    def __init__(self, memory_file: Path = MEMORY_FILE):
        self.memory_file = memory_file
        self.chroma_available = False
        self.collection = None
        self.embedding_model = None
        
        if CHROMA_AVAILABLE:
            try:
                self._initialize_chroma()
                self.chroma_available = True
                logger.info("ChromaDB initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB: {e}. Falling back to temporal-only retrieval.")
                self.chroma_available = False
        else:
            logger.warning("ChromaDB dependencies not installed. Using temporal-only retrieval.")
    
    def _initialize_chroma(self):
        """Initialize ChromaDB client and collection."""
        if not CHROMA_AVAILABLE:
            raise ImportError("ChromaDB not available")
        
        # Ensure chroma_db directory exists
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage (new API)
        try:
            # Try new API first (ChromaDB 0.4+)
            self.client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        except (AttributeError, TypeError):
            # Fallback to old API for compatibility
            try:
                settings = Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=str(CHROMA_DB_PATH)
                )
                self.client = chromadb.Client(settings)
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB with either API: {e}")
                raise
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity for embeddings
        )
        
        # Load embedding model
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded successfully")
    
    def get_recent_temporal_memories(self, count: int = 5) -> List[Dict]:
        """
        Get most recent N memories from JSON (temporal continuity).
        This always works as long as the JSON file exists.
        """
        if not self.memory_file.exists():
            return []
        
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                memories = json.loads(content)
            
            # Sort by date descending (most recent first)
            memories.sort(key=lambda m: m.get('date', ''), reverse=True)
            return memories[:count]
        except Exception as e:
            logger.error(f"Error loading recent temporal memories: {e}")
            return []
    
    def build_context_query(self, context_metadata: Dict) -> str:
        """
        Build semantic query from context metadata (weather, time, etc.).
        """
        parts = []
        
        if context_metadata:
            # Add weather information if available
            weather = context_metadata.get('weather')
            if weather:
                if isinstance(weather, dict):
                    # Extract key weather details
                    conditions = weather.get('currently', {}).get('summary', '')
                    if conditions:
                        parts.append(f"weather: {conditions}")
                elif isinstance(weather, str):
                    parts.append(f"weather: {weather}")
            
            # Add time of day if available
            time_of_day = context_metadata.get('time_of_day')
            if time_of_day:
                parts.append(f"time: {time_of_day}")
            
            # Add date/season context
            date_str = context_metadata.get('date')
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    month = date_obj.strftime('%B')
                    parts.append(f"month: {month}")
                except:
                    pass
        
        return " ".join(parts) if parts else "recent observations"
    
    def get_hybrid_memories(
        self,
        query_text: Optional[str] = None,
        recent_count: int = 5,
        semantic_top_k: int = 5,
        context_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Hybrid memory retrieval: combines recent temporal memories with semantically relevant ones.
        Always includes recent N memories for continuity, plus top-K semantically similar memories.
        Merges and deduplicates results.
        
        Args:
            query_text: Optional query text for semantic search (e.g., current weather, activity)
            recent_count: Number of most recent temporal memories to always include
            semantic_top_k: Number of top semantically relevant memories to retrieve
            context_metadata: Optional context (date, time, weather) to build query if query_text not provided
        
        Returns:
            List of unique memory dictionaries, sorted by date (most recent first)
        """
        all_memories = []
        seen_ids: Set[int] = set()
        
        # Step 1: Always get recent temporal memories (for continuity)
        # This never fails if JSON exists, ensuring we always have some memories
        recent_memories = self.get_recent_temporal_memories(count=recent_count)
        for mem in recent_memories:
            mem_id = mem.get('id')
            if mem_id is not None and mem_id not in seen_ids:
                # Ensure we have the text field (use llm_summary if available, else summary)
                mem_text = mem.get('llm_summary') or mem.get('summary') or mem.get('content', '')
                all_memories.append({
                    'id': mem_id,
                    'date': mem.get('date'),
                    'text': mem_text,
                    'source': 'temporal'
                })
                seen_ids.add(mem_id)
        
        # Step 2: Get semantically relevant memories (if Chroma available)
        semantic_memories = []
        if self.chroma_available and self.collection and self.embedding_model:
            try:
                # Build query text if not provided
                if not query_text and context_metadata:
                    query_text = self.build_context_query(context_metadata)
                
                if query_text:
                    # Embed the query
                    query_emb = self.embedding_model.encode(query_text).tolist()
                    
                    # Query ChromaDB
                    results = self.collection.query(
                        query_embeddings=[query_emb],
                        n_results=semantic_top_k
                    )
                    
                    # Extract results
                    if results and results.get('documents') and len(results['documents']) > 0:
                        documents = results['documents'][0]
                        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(documents)
                        
                        for doc, meta in zip(documents, metadatas):
                            mem_id = meta.get('id')
                            # Try to parse ID as int if it's a string
                            if isinstance(mem_id, str):
                                try:
                                    mem_id = int(mem_id)
                                except ValueError:
                                    continue
                            
                            if mem_id is not None and mem_id not in seen_ids:  # Deduplicate
                                semantic_memories.append({
                                    'id': mem_id,
                                    'date': meta.get('date'),
                                    'text': doc,
                                    'source': 'semantic'
                                })
                                seen_ids.add(mem_id)
                
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}, using temporal memories only")
        
        # Step 3: Merge and deduplicate
        all_memories.extend(semantic_memories)
        
        # Sort by date (most recent first)
        all_memories.sort(key=lambda m: m.get('date', ''), reverse=True)
        
        logger.info(f"Retrieved {len(all_memories)} hybrid memories ({len(recent_memories)} temporal, {len(semantic_memories)} semantic)")
        
        return all_memories
    
    def add_memory_to_chroma(self, memory: Dict) -> bool:
        """
        Add a new memory to ChromaDB.
        
        Args:
            memory: Memory dictionary with 'id', 'date', and 'llm_summary' or 'summary'
        
        Returns:
            True if successful, False otherwise
        """
        if not self.chroma_available or not self.collection or not self.embedding_model:
            return False
        
        try:
            # Get text to embed (prefer llm_summary, fallback to summary)
            text = memory.get('llm_summary') or memory.get('summary') or memory.get('content', '')
            if not text:
                logger.warning(f"Memory {memory.get('id')} has no text to embed")
                return False
            
            # Check if memory already exists in ChromaDB
            mem_id = str(memory.get('id'))
            existing = self.collection.get(ids=[mem_id])
            if existing and existing.get('ids') and len(existing['ids']) > 0:
                # Check if the existing document is just a placeholder (like "Entry X")
                existing_docs = existing.get('documents', [])
                if existing_docs and len(existing_docs) > 0:
                    existing_doc = existing_docs[0]
                    # If it's a placeholder, delete and re-add
                    if existing_doc.strip().startswith("Entry ") and len(existing_doc.strip()) < 20:
                        logger.debug(f"Memory {mem_id} has placeholder text, updating...")
                        self.collection.delete(ids=[mem_id])
                    else:
                        logger.debug(f"Memory {mem_id} already exists in ChromaDB, skipping")
                        return True
            
            # Generate embedding
            emb = self.embedding_model.encode(text)
            # Convert to list if it's a numpy array
            if hasattr(emb, 'tolist'):
                emb = emb.tolist()
            elif not isinstance(emb, list):
                emb = list(emb)
            
            # Add to ChromaDB
            self.collection.add(
                documents=[text],
                metadatas=[{
                    'id': memory.get('id'),
                    'date': memory.get('date', '')
                }],
                ids=[mem_id],
                embeddings=[emb]
            )
            
            logger.debug(f"Added memory {mem_id} to ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add memory to ChromaDB: {e}")
            return False
    
    def migrate_json_to_chroma(self) -> int:
        """
        Migrate all existing JSON memories to ChromaDB.
        Returns the number of memories migrated.
        """
        if not self.chroma_available:
            logger.error("ChromaDB not available, cannot migrate")
            return 0
        
        if not self.memory_file.exists():
            logger.warning(f"Memory file not found: {self.memory_file}")
            return 0
        
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return 0
                memories = json.loads(content)
            
            migrated = 0
            for mem in memories:
                if self.add_memory_to_chroma(mem):
                    migrated += 1
            
            logger.info(f"Migrated {migrated} memories to ChromaDB")
            return migrated
            
        except Exception as e:
            logger.error(f"Error migrating memories to ChromaDB: {e}")
            return 0
