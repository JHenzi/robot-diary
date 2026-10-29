#!/usr/bin/env bash
# Shared helpers for running robot-diary tasks inside the container.
#
# The container is the only supported runtime. The host venv is deliberately
# built without torch/chromadb/sentence-transformers, so anything that touches
# embeddings, Hugo or the deploy key must run in Docker - never on the host.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE="robot-diary"

cd "$PROJECT_ROOT"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# Run a command in the service container.
#
# Prefers exec into the already-running service. A `run --rm` would start a
# SECOND container on the same ./memory mount, and two processes writing
# chroma_db's sqlite file at once can corrupt it mid-observation.
#
# The docker check lives here, not at source time, so --help and usage errors
# do not block on the daemon.
in_container() {
    docker info >/dev/null 2>&1 || die "Docker is not running - start Docker Desktop and retry."

    local tty_flag=""
    [ -t 0 ] || tty_flag="-T"

    if [ -n "$(docker compose ps --status running -q "$SERVICE" 2>/dev/null)" ]; then
        docker compose exec ${tty_flag} "$SERVICE" "$@"
    else
        printf '%s is not running; using a one-off container.\n' "$SERVICE" >&2
        docker compose run --rm ${tty_flag} "$SERVICE" "$@"
    fi
}
