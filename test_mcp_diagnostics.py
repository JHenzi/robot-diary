#!/usr/bin/env python3
"""
Diagnostic script to test the hybrid memory retrieval system (MCP/ChromaDB).

This script will:
1. Check if ChromaDB is available
2. Test temporal memory retrieval
3. Test semantic memory retrieval  
4. Show what's in ChromaDB
5. Test adding a memory
6. Show detailed diagnostics
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.memory.retriever import HybridMemoryRetriever, CHROMA_AVAILABLE
from src.memory.manager import MemoryManager
from src.context.metadata import get_context_metadata
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_chromadb_availability():
    """Test 1: Check if ChromaDB is available."""
    print_section("TEST 1: ChromaDB Availability")
    
    if CHROMA_AVAILABLE:
        print("✅ ChromaDB dependencies are installed")
        try:
            import chromadb
            import sentence_transformers
            print(f"   - chromadb version: {chromadb.__version__ if hasattr(chromadb, '__version__') else 'unknown'}")
            print(f"   - sentence-transformers available")
        except Exception as e:
            print(f"   ⚠️  Error importing: {e}")
    else:
        print("❌ ChromaDB dependencies NOT installed")
        print("   Install with: pip install chromadb sentence-transformers")
        return False
    
    return True


def test_retriever_initialization():
    """Test 2: Initialize the retriever."""
    print_section("TEST 2: Retriever Initialization")
    
    try:
        retriever = HybridMemoryRetriever()
        
        if retriever.chroma_available:
            print("✅ ChromaDB initialized successfully")
            print(f"   - Collection name: {retriever.collection.name if retriever.collection else 'None'}")
            print(f"   - Embedding model: {retriever.embedding_model.get_sentence_embedding_dimension() if retriever.embedding_model else 'None'} dimensions")
            return retriever
        else:
            print("⚠️  ChromaDB not available, using temporal-only mode")
            print("   (This is OK - system will fall back to JSON-only retrieval)")
            return retriever
            
    except Exception as e:
        print(f"❌ Failed to initialize retriever: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_temporal_memories(retriever):
    """Test 3: Test temporal memory retrieval."""
    print_section("TEST 3: Temporal Memory Retrieval")
    
    if not retriever:
        print("❌ Retriever not initialized")
        return
    
    try:
        memories = retriever.get_recent_temporal_memories(count=5)
        print(f"✅ Retrieved {len(memories)} temporal memories")
        
        if memories:
            print("\n   Recent temporal memories:")
            for mem in memories[:3]:  # Show first 3
                mem_id = mem.get('id', '?')
                date = mem.get('date', 'Unknown')
                summary = mem.get('llm_summary') or mem.get('summary', 'No summary')[:80]
                print(f"   - ID {mem_id} ({date}): {summary}...")
        else:
            print("   ⚠️  No memories found in observations.json")
            
    except Exception as e:
        print(f"❌ Error retrieving temporal memories: {e}")
        import traceback
        traceback.print_exc()


def test_chromadb_contents(retriever):
    """Test 4: Check what's in ChromaDB."""
    print_section("TEST 4: ChromaDB Contents")
    
    if not retriever or not retriever.chroma_available:
        print("⚠️  ChromaDB not available, skipping")
        return
    
    try:
        # Get collection count
        count = retriever.collection.count()
        print(f"✅ ChromaDB collection has {count} memories")
        
        if count > 0:
            # Get a few sample documents
            results = retriever.collection.get(limit=5)
            if results and results.get('documents'):
                print("\n   Sample documents in ChromaDB:")
                for i, (doc, meta) in enumerate(zip(results['documents'], results.get('metadatas', [{}] * len(results['documents'])))):
                    mem_id = meta.get('id', '?')
                    doc_preview = doc[:100] if doc else 'Empty'
                    # Check if it's a placeholder
                    is_placeholder = doc.strip().startswith("Entry ") and len(doc.strip()) < 20
                    status = "⚠️ PLACEHOLDER" if is_placeholder else "✅"
                    print(f"   {status} ID {mem_id}: {doc_preview}...")
        else:
            print("   ⚠️  ChromaDB is empty - run migration script:")
            print("      python migrate_memories_to_chroma.py --force")
            
    except Exception as e:
        print(f"❌ Error checking ChromaDB contents: {e}")
        import traceback
        traceback.print_exc()


def test_semantic_search(retriever):
    """Test 5: Test semantic search."""
    print_section("TEST 5: Semantic Search")
    
    if not retriever or not retriever.chroma_available:
        print("⚠️  ChromaDB not available, skipping")
        return
    
    try:
        # Test with a simple query
        query = "weather observation clear sky"
        print(f"   Testing query: '{query}'")
        
        memories = retriever.get_hybrid_memories(
            query_text=query,
            recent_count=3,
            semantic_top_k=3
        )
        
        print(f"✅ Retrieved {len(memories)} hybrid memories")
        
        # Count by source
        temporal_count = sum(1 for m in memories if m.get('source') == 'temporal')
        semantic_count = sum(1 for m in memories if m.get('source') == 'semantic')
        
        print(f"   - Temporal: {temporal_count}")
        print(f"   - Semantic: {semantic_count}")
        
        if semantic_count > 0:
            print("\n   Semantic results:")
            for mem in memories:
                if mem.get('source') == 'semantic':
                    mem_id = mem.get('id', '?')
                    text = mem.get('text', '')[:80]
                    print(f"   - ID {mem_id}: {text}...")
        else:
            print("   ⚠️  No semantic results (ChromaDB may be empty or query didn't match)")
            
    except Exception as e:
        print(f"❌ Error in semantic search: {e}")
        import traceback
        traceback.print_exc()


def test_hybrid_retrieval_with_context(retriever):
    """Test 6: Test hybrid retrieval with context metadata."""
    print_section("TEST 6: Hybrid Retrieval with Context")
    
    if not retriever:
        print("❌ Retriever not initialized")
        return
    
    try:
        # Create sample context
        context_metadata = get_context_metadata()
        print(f"   Context: {context_metadata.get('season')} {context_metadata.get('time_of_day')}")
        if context_metadata.get('weather'):
            weather = context_metadata['weather']
            if isinstance(weather, dict):
                summary = weather.get('currently', {}).get('summary', 'N/A')
                print(f"   Weather: {summary}")
        
        memories = retriever.get_hybrid_memories(
            recent_count=5,
            semantic_top_k=5,
            context_metadata=context_metadata
        )
        
        print(f"✅ Retrieved {len(memories)} hybrid memories")
        
        # Show breakdown
        temporal = [m for m in memories if m.get('source') == 'temporal']
        semantic = [m for m in memories if m.get('source') == 'semantic']
        
        print(f"   - Temporal memories: {len(temporal)}")
        if temporal:
            print(f"     Most recent: ID {temporal[0].get('id')}")
        
        print(f"   - Semantic memories: {len(semantic)}")
        if semantic:
            print(f"     Examples:")
            for mem in semantic[:2]:
                mem_id = mem.get('id', '?')
                text = mem.get('text', '')[:60]
                print(f"       ID {mem_id}: {text}...")
                
    except Exception as e:
        print(f"❌ Error in hybrid retrieval: {e}")
        import traceback
        traceback.print_exc()


def test_memory_manager_integration():
    """Test 7: Test MemoryManager integration."""
    print_section("TEST 7: MemoryManager Integration")
    
    try:
        manager = MemoryManager()
        memory_count = manager.get_total_count()
        print(f"✅ MemoryManager initialized")
        print(f"   - Total observations: {memory_count}")
        
        # Test hybrid retrieval through manager
        memories = manager.get_hybrid_memories(
            recent_count=3,
            semantic_top_k=3
        )
        
        print(f"✅ Retrieved {len(memories)} memories via MemoryManager")
        
        if memories:
            print("\n   Memory breakdown:")
            for mem in memories[:3]:
                mem_id = mem.get('id', '?')
                source = mem.get('source', 'unknown')
                text = mem.get('text', '')[:60]
                print(f"   - [{source}] ID {mem_id}: {text}...")
                
    except Exception as e:
        print(f"❌ Error in MemoryManager integration: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all diagnostic tests."""
    print("\n" + "=" * 60)
    print("  MCP / Hybrid Memory Retrieval Diagnostics")
    print("=" * 60)
    
    # Test 1: Check availability
    if not test_chromadb_availability():
        print("\n⚠️  ChromaDB not available - system will use temporal-only mode")
        print("   This is OK, but semantic search will be disabled.")
        return
    
    # Test 2: Initialize
    retriever = test_retriever_initialization()
    
    # Test 3: Temporal memories
    test_temporal_memories(retriever)
    
    # Test 4: ChromaDB contents
    test_chromadb_contents(retriever)
    
    # Test 5: Semantic search
    test_semantic_search(retriever)
    
    # Test 6: Hybrid with context
    test_hybrid_retrieval_with_context(retriever)
    
    # Test 7: MemoryManager integration
    test_memory_manager_integration()
    
    # Summary
    print_section("SUMMARY")
    if retriever and retriever.chroma_available:
        count = retriever.collection.count() if retriever.collection else 0
        if count > 0:
            print("✅ Hybrid memory system is WORKING")
            print(f"   - ChromaDB has {count} memories")
            print("   - Semantic search is enabled")
        else:
            print("⚠️  ChromaDB is initialized but EMPTY")
            print("   Run: python migrate_memories_to_chroma.py --force")
    else:
        print("⚠️  Using temporal-only mode (ChromaDB not available)")
        print("   Install: pip install chromadb sentence-transformers")
    
    print("\n")


if __name__ == "__main__":
    main()


