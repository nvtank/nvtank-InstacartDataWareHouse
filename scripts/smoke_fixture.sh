#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly PROJECT_NAME="${SMOKE_PROJECT_NAME:-instacart-fixture-smoke}"
readonly DB_PORT="${SMOKE_DB_PORT:-33307}"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

case "$PROJECT_NAME" in
    instacart-fixture-smoke | instacart-fixture-smoke-*) ;;
    *) die "SMOKE_PROJECT_NAME must start with instacart-fixture-smoke" ;;
esac
[[ "$DB_PORT" =~ ^[0-9]+$ ]] || die "SMOKE_DB_PORT must be an integer"
((DB_PORT >= 1024 && DB_PORT <= 65535)) || die "SMOKE_DB_PORT must be between 1024 and 65535"

export DB_PORT
export DB_NAME=instacart_dwh
export DB_USER=instacart
export DB_PASSWORD=instacart-fixture-password
export MARIADB_ROOT_PASSWORD=instacart-fixture-root-password
export COMPOSE_PROJECT_NAME="$PROJECT_NAME"

readonly -a COMPOSE=(
    docker compose
    --project-directory "$PROJECT_ROOT"
    --project-name "$PROJECT_NAME"
    --profile live
    --profile tools
)

cleanup() {
    "${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

printf '[1/5] Starting isolated MariaDB schema\n'
"${COMPOSE[@]}" up --detach --wait mariadb

printf '[2/5] Reapplying the idempotent schema workflow\n'
"${PROJECT_ROOT}/sql/run_all_sql.sh" >/dev/null

printf '[3/5] Loading deterministic CSV fixture\n'
"${COMPOSE[@]}" run --rm --build \
    --env DATA_PATH=/app/fixtures \
    --volume "${PROJECT_ROOT}/tests/fixtures/data:/app/fixtures:ro" \
    etl

printf '[4/5] Re-running warehouse contracts\n'
"${COMPOSE[@]}" run --rm --no-deps etl --validate-only

printf '[5/5] Reconciling exact fixture counts\n'
actual_counts="$("${COMPOSE[@]}" exec --no-TTY mariadb sh -ec '
    MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb \
        --protocol=socket \
        --user="$MARIADB_USER" \
        --database="$MARIADB_DATABASE" \
        --batch \
        --skip-column-names \
        --execute="
            SELECT label, row_count
            FROM (
                SELECT 1 AS sort_order, \"Dim_Aisle\" AS label, COUNT(*) AS row_count FROM Dim_Aisle
                UNION ALL SELECT 2, \"Dim_Department\", COUNT(*) FROM Dim_Department
                UNION ALL SELECT 3, \"Dim_Product\", COUNT(*) FROM Dim_Product
                UNION ALL SELECT 4, \"Dim_Time\", COUNT(*) FROM Dim_Time
                UNION ALL SELECT 5, \"Dim_User\", COUNT(*) FROM Dim_User
                UNION ALL SELECT 6, \"Fact_Order_Details\", COUNT(*) FROM Fact_Order_Details
                UNION ALL SELECT 7, \"Fact_Orders\", COUNT(*) FROM Fact_Orders
            ) fixture_counts
            ORDER BY sort_order;
        "
')"

readonly EXPECTED_COUNTS=$'Dim_Aisle\t2\nDim_Department\t2\nDim_Product\t4\nDim_Time\t168\nDim_User\t2\nFact_Order_Details\t11\nFact_Orders\t5'
if [[ "$actual_counts" != "$EXPECTED_COUNTS" ]]; then
    printf 'Expected:\n%s\nActual:\n%s\n' "$EXPECTED_COUNTS" "$actual_counts" >&2
    die "fixture row counts did not reconcile"
fi

printf 'Fixture smoke test passed: 7 tables reconciled and all quality contracts passed.\n'
