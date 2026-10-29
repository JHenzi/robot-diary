#!/usr/bin/env bash
# Trigger one observation cycle in the container.
# Args pass through to observe_now.py: --use-cache, --news-only, --simulate.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
in_container python observe_now.py "$@"
