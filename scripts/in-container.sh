#!/usr/bin/env bash
# Escape hatch: run any command in the service container.
#   ./scripts/in-container.sh python audit_backstory.py
#   ./scripts/in-container.sh bash
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[ "$#" -gt 0 ] || set -- bash
in_container "$@"
