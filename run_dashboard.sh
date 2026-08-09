#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

resolve_python() {
    if [[ -n "${PYTHON_BIN:-}" ]]; then
        [[ -x "$PYTHON_BIN" ]] || die "PYTHON_BIN is not executable: $PYTHON_BIN"
        printf '%s\n' "$PYTHON_BIN"
        return
    fi

    if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
        printf '%s\n' "${VIRTUAL_ENV}/bin/python"
        return
    fi

    if [[ -x ".venv/bin/python" ]]; then
        printf '%s\n' ".venv/bin/python"
        return
    fi

    if [[ -x "venv/bin/python" ]]; then
        printf '%s\n' "venv/bin/python"
        return
    fi

    command -v python3 || die \
        "Python is unavailable. Create the environment before starting the dashboard."
}

readonly PYTHON="$(resolve_python)"

if ! "$PYTHON" -c "import streamlit" >/dev/null 2>&1; then
    die "Dashboard dependencies are missing. Install the project once with 'pip install .'."
fi

readonly MODE="${DASHBOARD_MODE:-auto}"
readonly ADDRESS="${STREAMLIT_SERVER_ADDRESS:-127.0.0.1}"
readonly PORT="${STREAMLIT_SERVER_PORT:-8501}"

case "$MODE" in
    auto | demo | live) ;;
    *) die "DASHBOARD_MODE must be one of: auto, demo, live" ;;
esac

[[ "$PORT" =~ ^[0-9]+$ ]] || die "STREAMLIT_SERVER_PORT must be an integer"
((PORT >= 1 && PORT <= 65535)) || die "STREAMLIT_SERVER_PORT must be between 1 and 65535"

printf 'Starting Instacart Decision Intelligence\n'
printf '  mode: %s\n' "$MODE"
printf '  URL:  http://%s:%s\n' "$ADDRESS" "$PORT"

exec "$PYTHON" -m streamlit run dashboard/app.py \
    --server.address "$ADDRESS" \
    --server.port "$PORT" \
    --server.headless true \
    "$@"
