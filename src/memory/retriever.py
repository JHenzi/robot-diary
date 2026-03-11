"""Hybrid memory retrieval using ChromaDB for semantic search and temporal continuity."""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
from datetime import datetime

# Disable ChromaDB telemetry before importing
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

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
    SentenceTransformer = None
    logging.warning("ChromaDB or sentence-transformers not available. Semantic search will be disabled.")

from ..config import MEMORY_DIR, PROJECT_ROOT, IMAGES_DIR

logger = logging.getLogger(__name__)

MEMORY_FILE = MEMORY_DIR / 'observations.json'
CHROMA_DB_PATH = MEMORY_DIR / 'chroma_db'
COLLECTION_NAME = "robot_memories"
IMAGE_COLLECTION_NAME = "robot_image_embeddings"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # Lightweight, local embedding model
IMAGE_EMBEDDING_MODEL_NAME = "clip-ViT-B-32"  # CLIP model for image embeddings
MODEL_LOCAL_FIRST = os.getenv('SENTENCE_TRANSFORMERS_LOCAL_FIRST', 'true').lower() == 'true'

# Process-level model cache so repeated observation cycles don't re-initialize
# the same SentenceTransformer objects.
_MODEL_CACHE: Dict[str, Any] = {}


def _get_sentence_transformer(model_name: str):
    """
    Load SentenceTransformer with process-level caching.

    Strategy:
    1. Reuse cached model object if already loaded in this process.
    2. Try local cache only first to avoid repeated Hugging Face HEAD requests.
    3. Fall back to network fetch only if local model files are missing.
    """
    cached_model = _MODEL_CACHE.get(model_name)
    if cached_model is not None:
        logger.debug(f"Reusing cached embedding model: {model_name}")
        return cached_model

    if SentenceTransformer is None:
        raise ImportError("sentence-transformers is not available")

    model = None

    if MODEL_LOCAL_FIRST:
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
            logger.info(f"Loaded embedding model from local cache: {model_name}")
        except TypeError:
            # Older sentence-transformers versions may not support local_files_only.
            logger.debug("SentenceTransformer does not support local_files_only; using default loading")
        except Exception as e:
            logger.info(f"Local cache unavailable for {model_name}, falling back to download: {e}")

    if model is None:
        model = SentenceTransformer(model_name)
        logger.info(f"Loaded embedding model with network fallback: {model_name}")

    _MODEL_CACHE[model_name] = model
    return model


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
        self.image_collection = None
        self.embedding_model = None
        self.image_embedding_model = None
        
        if CHROMA_AVAILABLE:
            try:
                self._initialize_chroma()
                self.chroma_available = True
                logger.info("ChromaDB initialized successfully")
            except Exception as e:
                # Catch all exceptions including PanicException from Rust bindings via pyo3
                # PanicException is a subclass of Exception, so this will catch it
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
        
        # Load text embedding model
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        self.embedding_model = _get_sentence_transformer(EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded successfully")
        
        # Get or create image embedding collection
        try:
            self.image_collection = self.client.get_or_create_collection(
                name=IMAGE_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity for embeddings
            )
            
            # Load image embedding model (CLIP)
            logger.info(f"Loading image embedding model: {IMAGE_EMBEDDING_MODEL_NAME}")
            self.image_embedding_model = _get_sentence_transformer(IMAGE_EMBEDDING_MODEL_NAME)
            logger.info("Image embedding model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize image embedding model: {e}")
            self.image_embedding_model = None
            self.image_collection = None
    
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
    
    def get_memories_by_time_slot(self, observation_type: str, count: int = 5) -> List[Dict]:
        """
        Get memories filtered by observation type (time slot).
        
        Args:
            observation_type: "morning" or "evening"
            count: Number of memories to return
            
        Returns:
            List of memory dictionaries matching the time slot, sorted by date descending
        """
        if not self.memory_file.exists():
            return []
        
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                memories = json.loads(content)
            
            filtered = []
            for mem in memories:
                # Try to get observation_type from memory if stored
                mem_obs_type = mem.get('observation_type')
                
                # If not stored, try to infer from date/time
                if mem_obs_type is None:
                    try:
                        date_str = mem.get('date', '')
                        if date_str:
                            # Parse ISO format datetime
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            hour = dt.hour
                            # Infer: morning is roughly 5-12, evening is 12-5
                            if 5 <= hour < 12:
                                mem_obs_type = 'morning'
                            else:
                                mem_obs_type = 'evening'
                    except Exception:
                        # If we can't parse, skip this memory
                        continue
                
                if mem_obs_type == observation_type:
                    filtered.append(mem)
            
            # Sort by date descending (most recent first)
            filtered.sort(key=lambda m: m.get('date', ''), reverse=True)
            return filtered[:count]
        except Exception as e:
            logger.error(f"Error loading memories by time slot: {e}")
            return []
    
    def get_image_embeddings_for_memories(self, memory_ids: List[int]) -> List[tuple]:
        """
        Retrieve image embeddings from ChromaDB for given memory IDs.
        
        Args:
            memory_ids: List of memory IDs to retrieve embeddings for
            
        Returns:
            List of tuples: (memory_id, embedding_vector)
        """
        if not self.chroma_available or not self.image_collection:
            return []
        
        try:
            ids_str = [str(mid) for mid in memory_ids]
            results = self.image_collection.get(
                ids=ids_str,
                include=['embeddings']
            )
            
            if not results or not results.get('ids'):
                return []
            
            embeddings_list = []
            ids = results.get('ids', [])
            embeddings = results.get('embeddings', [])
            
            for mem_id_str, emb in zip(ids, embeddings):
                try:
                    mem_id = int(mem_id_str)
                    embeddings_list.append((mem_id, emb))
                except ValueError:
                    continue
            
            return embeddings_list
        except Exception as e:
            logger.warning(f"Error retrieving image embeddings: {e}")
            return []
    
    def _resolve_image_path(self, image_path_str: str) -> Optional[Path]:
        """
        Resolve image path, handling Docker paths and relative paths.
        
        Args:
            image_path_str: Image path from memory (could be Docker path, relative, or absolute)
            
        Returns:
            Resolved Path object, or None if path cannot be resolved
        """
        # Try the path as-is first
        path = Path(image_path_str)
        if path.exists():
            return path
        
        # If it's a Docker path (/app/images/...), convert to local
        if str(path).startswith('/app/images/'):
            filename = path.name
            local_path = IMAGES_DIR / filename
            if local_path.exists():
                return local_path
        
        # If it's just a filename, look in IMAGES_DIR
        if not str(path).startswith('/') and '/' not in str(path):
            local_path = IMAGES_DIR / path
            if local_path.exists():
                return local_path
        
        # Try relative to PROJECT_ROOT
        relative_path = PROJECT_ROOT / path
        if relative_path.exists():
            return relative_path
        
        # Try relative to IMAGES_DIR if path has subdirectories
        if '/' in str(path) and not str(path).startswith('/'):
            local_path = IMAGES_DIR / path
            if local_path.exists():
                return local_path
        
        return None
    
    def generate_image_embedding(self, image_path: Path) -> Optional[List[float]]:
        """
        Generate embedding for a single image using CLIP model.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Embedding vector as list of floats, or None on failure
        """
        if not self.image_embedding_model:
            return None
        
        if not image_path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None
        
        try:
            from PIL import Image
            import numpy as np
            
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')
            
            # Generate embedding
            emb = self.image_embedding_model.encode(image)
            
            # Convert to list if it's a numpy array
            if hasattr(emb, 'tolist'):
                emb = emb.tolist()
            elif not isinstance(emb, list):
                emb = list(emb)
            
            return emb
        except Exception as e:
            logger.warning(f"Error generating image embedding: {e}")
            return None
    
    def calculate_circadian_boredom(self, image_path: Path, context_metadata: Dict) -> Optional[float]:
        """
        Calculate circadian boredom factor by comparing current image embedding
        with last 5 same time-slot image embeddings.
        
        Args:
            image_path: Path to current observation image
            context_metadata: Dictionary with observation_type and other context
            
        Returns:
            Average cosine similarity (boredom factor) or None if insufficient data
        """
        if not self.chroma_available or not self.image_embedding_model or not self.image_collection:
            return None
        
        # Extract observation_type
        observation_type = context_metadata.get('observation_type', 'evening')
        
        # Get last 5 same time-slot memories
        memories = self.get_memories_by_time_slot(observation_type, count=5)
        
        if len(memories) < 5:
            logger.debug(f"Not enough memories for time slot '{observation_type}': {len(memories)} < 5")
            return None
        
        # Generate current image embedding
        current_emb = self.generate_image_embedding(image_path)
        if current_emb is None:
            logger.warning("Failed to generate current image embedding")
            return None
        
        # Get memory IDs
        memory_ids = [mem.get('id') for mem in memories if mem.get('id') is not None]
        
        # Retrieve or generate embeddings for past images
        past_embeddings = self.get_image_embeddings_for_memories(memory_ids)
        
        # If we don't have embeddings stored, try to generate them from image paths
        if len(past_embeddings) < len(memory_ids):
            logger.debug(f"Only {len(past_embeddings)}/{len(memory_ids)} embeddings found, generating missing ones...")
            for mem in memories:
                mem_id = mem.get('id')
                if mem_id is None:
                    continue
                
                # Check if we already have this embedding
                if any(pid == mem_id for pid, _ in past_embeddings):
                    continue
                
                # Try to generate from image_path
                image_path_str = mem.get('image_path')
                if image_path_str:
                    try:
                        mem_image_path = self._resolve_image_path(image_path_str)
                        if mem_image_path and mem_image_path.exists():
                            emb = self.generate_image_embedding(mem_image_path)
                            if emb:
                                past_embeddings.append((mem_id, emb))
                                # Store the embedding for future use
                                try:
                                    self.add_image_embedding_to_chroma(mem, mem_image_path)
                                except Exception as e:
                                    logger.debug(f"Could not store embedding for memory {mem_id}: {e}")
                    except Exception as e:
                        logger.debug(f"Could not generate embedding for memory {mem_id}: {e}")
                        continue
        
        if len(past_embeddings) < 5:
            logger.debug(f"Not enough past embeddings: {len(past_embeddings)} < 5")
            return None
        
        # Calculate cosine similarities
        import numpy as np
        
        similarities = []
        current_emb_np = np.array(current_emb)
        current_norm = np.linalg.norm(current_emb_np)
        
        for mem_id, past_emb in past_embeddings[:5]:  # Use first 5
            try:
                past_emb_np = np.array(past_emb)
                past_norm = np.linalg.norm(past_emb_np)
                
                if current_norm == 0 or past_norm == 0:
                    continue
                
                # Cosine similarity: dot product / (norm1 * norm2)
                similarity = np.dot(current_emb_np, past_emb_np) / (current_norm * past_norm)
                similarities.append(float(similarity))
            except Exception as e:
                logger.debug(f"Error calculating similarity for memory {mem_id}: {e}")
                continue
        
        if len(similarities) < 5:
            logger.debug(f"Not enough valid similarities: {len(similarities)} < 5")
            return None
        
        # Return average (boredom factor)
        boredom_factor = sum(similarities) / len(similarities)
        return boredom_factor
    
    def add_image_embedding_to_chroma(self, memory: Dict, image_path) -> bool:
        """
        Generate and store image embedding when observation is saved.
        
        Args:
            memory: Memory dictionary with 'id', 'date', 'observation_type'
            image_path: Path to the image file (Path object or string) (can be Path object or string)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.chroma_available or not self.image_collection or not self.image_embedding_model:
            return False
        
        # Resolve path if it's a string or Docker path
        if isinstance(image_path, str):
            resolved_path = self._resolve_image_path(image_path)
            if resolved_path is None:
                logger.warning(f"Image file not found for embedding: {image_path}")
                return False
            image_path = resolved_path
        elif not image_path.exists():
            # Try to resolve if it doesn't exist
            resolved_path = self._resolve_image_path(str(image_path))
            if resolved_path is None:
                logger.warning(f"Image file not found for embedding: {image_path}")
                return False
            image_path = resolved_path
        
        try:
            mem_id = str(memory.get('id'))
            if not mem_id:
                return False
            
            # Check if embedding already exists
            existing = self.image_collection.get(ids=[mem_id])
            if existing and existing.get('ids') and len(existing['ids']) > 0:
                logger.debug(f"Image embedding {mem_id} already exists in ChromaDB, skipping")
                return True
            
            # Generate embedding
            emb = self.generate_image_embedding(image_path)
            if emb is None:
                logger.warning(f"Failed to generate image embedding for memory {mem_id}")
                return False
            
            # Get observation_type from memory or context
            observation_type = memory.get('observation_type', 'evening')
            
            # Add to ChromaDB
            self.image_collection.add(
                documents=[str(image_path)],  # Store image path as document
                metadatas=[{
                    'id': memory.get('id'),
                    'date': memory.get('date', ''),
                    'observation_type': observation_type
                }],
                ids=[mem_id],
                embeddings=[emb]
            )
            
            logger.debug(f"Added image embedding {mem_id} to ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add image embedding to ChromaDB: {e}")
            return False
