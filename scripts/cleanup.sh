#!/usr/bin/env bash
# DESTRUCTIVE: wipes memories, images and Hugo posts, then rebuilds the site.
# cleanup.py prompts for confirmation; run this from a terminal, not a pipe.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
[ -t 0 ] || die "cleanup needs an interactive terminal to confirm."
in_container python cleanup.py "$@"
