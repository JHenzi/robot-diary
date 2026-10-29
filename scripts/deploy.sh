#!/usr/bin/env bash
# Build the Hugo site and rsync it to the web host.
# Container-only: the hugo binary and the mounted deploy key live there.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
in_container python deploy.py "$@"
