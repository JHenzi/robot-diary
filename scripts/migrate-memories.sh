#!/usr/bin/env bash
# Backfill observations.json into the ChromaDB collection.
# Needs real MiniLM embeddings, so it is container-only.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
in_container python migrate_memories_to_chroma.py "$@"
