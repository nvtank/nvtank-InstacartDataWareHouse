#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly TOTAL_STEPS=11
readonly -a COMPOSE=(
    docker compose
    --project-directory "$PROJECT_ROOT"
    --profile live
)

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

on_error() {
    local exit_code=$?
    printf 'error: schema setup failed at line %s\n' "$1" >&2
    exit "$exit_code"
}
trap 'on_error "$LINENO"' ERR

command -v docker >/dev/null 2>&1 || die "Docker is required to apply the schema."

readonly CONTAINER_ID="$("${COMPOSE[@]}" ps --status running --quiet mariadb)"
[[ -n "$CONTAINER_ID" ]] || die "MariaDB is not running. Run 'make db' first."

run_root_client() {
    "${COMPOSE[@]}" exec --no-TTY mariadb sh -ec '
        : "${MARIADB_ROOT_PASSWORD:?MARIADB_ROOT_PASSWORD is not configured}"
        MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb \
            --protocol=socket \
            --user=root
    '
}

run_app_client() {
    "${COMPOSE[@]}" exec --no-TTY mariadb sh -ec '
        : "${MARIADB_USER:?MARIADB_USER is not configured}"
        : "${MARIADB_PASSWORD:?MARIADB_PASSWORD is not configured}"
        : "${MARIADB_DATABASE:?MARIADB_DATABASE is not configured}"
        MYSQL_PWD="$MARIADB_PASSWORD" exec mariadb \
            --protocol=socket \
            --user="$MARIADB_USER" \
            --database="$MARIADB_DATABASE"
    '
}

readonly -a SCHEMA_FILES=(
    "01_create_database.sql"
    "02_dim_time.sql"
    "03_dim_department.sql"
    "04_dim_aisle.sql"
    "05_dim_product.sql"
    "06_dim_user.sql"
    "07_fact_orders.sql"
    "08_fact_order_details.sql"
    "09_additional_indexes.sql"
)

printf '[1/%d] Checking MariaDB connectivity\n' "$TOTAL_STEPS"
if ! run_root_client <<<"SELECT 1;" >/dev/null; then
    die "MariaDB rejected the container-managed root credentials."
fi

step=2
for file_name in "${SCHEMA_FILES[@]}"; do
    file_path="${SCRIPT_DIR}/${file_name}"
    [[ -f "$file_path" ]] || die "SQL file not found: $file_path"
    printf '[%d/%d] Applying %s\n' "$step" "$TOTAL_STEPS" "$file_name"
    if [[ "$file_name" == "01_create_database.sql" ]]; then
        run_root_client <"$file_path"
    else
        run_app_client <"$file_path"
    fi
    ((step += 1))
done

printf '[11/%d] Verifying required tables and partitions\n' "$TOTAL_STEPS"
run_app_client <<'SQL'
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME;

SELECT TABLE_NAME, COUNT(*) AS partition_count
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_SCHEMA = DATABASE()
  AND PARTITION_NAME IS NOT NULL
GROUP BY TABLE_NAME
ORDER BY TABLE_NAME;
SQL

printf 'Warehouse schema is ready. Next: make etl\n'
