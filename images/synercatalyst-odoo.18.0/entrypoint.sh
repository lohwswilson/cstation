#!/bin/bash
set -e

: ${HOST:=${DB_PORT_5432_TCP_ADDR:='db'}}
: ${PORT:=${DB_PORT_5432_TCP_PORT:=5432}}
: ${USER:=${DB_ENV_POSTGRES_USER:=${POSTGRES_USER:='odoo'}}}
: ${PASSWORD:=${DB_ENV_POSTGRES_PASSWORD:=${POSTGRES_PASSWORD:=''}}}

DB_ARGS=()
function check_config() {
    param="$1"
    value="$2"
    if [ -n "$value" ] && [ "$value" != "False" ]; then
        if ! grep -q -E "^\s*\b${param}\b\s*=" "$ODOO_RC" 2>/dev/null; then
            DB_ARGS+=("--${param}")
            DB_ARGS+=("${value}")
        fi
    fi
}
check_config "db_host" "$HOST"
check_config "db_port" "$PORT"
check_config "db_user" "$USER"
if [ -n "$PASSWORD" ]; then
    check_config "db_password" "$PASSWORD"
fi

if [ -f /usr/local/bin/wait-for-psql.py ] && [ -n "$HOST" ] && [ "$HOST" != "False" ]; then
    python3 /usr/local/bin/wait-for-psql.py "${DB_ARGS[@]}" --timeout=15 || true
fi

case "$1" in
    -- | odoo)
        shift
        if [[ "$1" == "scaffold" ]] ; then
            exec odoo "$@"
        else
            exec odoo "$@" "${DB_ARGS[@]}"
        fi
        ;;
    -*)
        exec odoo "$@" "${DB_ARGS[@]}"
        ;;
    *)
        exec "$@"
esac

exit 1
