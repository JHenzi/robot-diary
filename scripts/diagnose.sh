#!/usr/bin/env bash
# Run one of the standalone diagnostic scripts inside the container.
#
# These live at the repo root and are named test_*.py, but they are NOT part of
# the pytest suite - pytest.ini sets `testpaths = tests`, so pytest never
# collects them. They are one-off checks, and each needs something only the
# container has (embeddings, the hugo binary, deno for yt-dlp, the deploy key).
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

usage() {
    cat <<'USAGE'
usage: diagnose.sh <check> [args...]

checks:
  backstory          audit_backstory.py
  deploy             test_deploy.py
  fallback           verify_fallback.py
  fallback-failure   test_fallback_with_failure.py
  holidays           debug_holidays.py
  image              test_image_fetch.py
  mcp                test_mcp_diagnostics.py
  randomizations     test_randomizations.py
USAGE
}

[ "$#" -gt 0 ] || { usage; exit 2; }

check="$1"; shift
case "$check" in
    backstory)        script=audit_backstory.py ;;
    deploy)           script=test_deploy.py ;;
    fallback)         script=verify_fallback.py ;;
    fallback-failure) script=test_fallback_with_failure.py ;;
    holidays)         script=debug_holidays.py ;;
    image)            script=test_image_fetch.py ;;
    mcp)              script=test_mcp_diagnostics.py ;;
    randomizations)   script=test_randomizations.py ;;
    -h|--help)        usage; exit 0 ;;
    *) printf 'unknown check: %s\n\n' "$check" >&2; usage >&2; exit 2 ;;
esac

in_container python "$script" "$@"
