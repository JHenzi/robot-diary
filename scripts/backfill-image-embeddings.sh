#!/usr/bin/env bash
# Backfill CLIP image embeddings for saved webcam frames.
# Needs real clip-ViT-B-32 embeddings, so it is container-only.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
in_container python backfill_image_embeddings.py "$@"
