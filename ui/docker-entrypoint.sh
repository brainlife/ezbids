#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNTIME_ENV_FILE="${SCRIPT_DIR}/public/runtime-env.js"

cat > "${RUNTIME_ENV_FILE}" <<EOF
(() => {
    const existing = window.env || {};

    window.env = {
        API_HOST: "\${API_HOST:-/api/ezbids}" || existing.API_HOST || '/api/ezbids',
        IS_ELECTRON: "\${IS_ELECTRON:-false}" || existing.IS_ELECTRON || 'false',
        BRAINLIFE_AUTHENTICATION: "\${BRAINLIFE_AUTHENTICATION:-false}" || existing.BRAINLIFE_AUTHENTICATION || 'false',
    };
})();
EOF

exec "$@"
