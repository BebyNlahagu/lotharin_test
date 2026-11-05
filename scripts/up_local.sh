#!/usr/bin/env bash
# Installs the module (+ seed data from demo/, loaded because the new database has demo mode on) on an EMPTY database and starts Odoo 18 (no Docker).
# Variables (all optional): ODOO_DIR (Odoo source), VENV (virtualenv), DB (database name).
set -euo pipefail
cd "$(dirname "$0")/.."
ODOO_DIR="${ODOO_DIR:-$HOME/odoo18}"
VENV="${VENV:-$HOME/odoo18-venv}"
DB="${DB:-rc_demo}"
ADDONS="$ODOO_DIR/addons,$ODOO_DIR/odoo/addons,$(pwd)/addons"
"$VENV/bin/python" "$ODOO_DIR/odoo-bin" -d "$DB" --addons-path="$ADDONS" \
  -i reseller_commission --stop-after-init
echo "Installed. Starting Odoo: http://localhost:8069 (database: $DB, login: admin / admin)"
exec "$VENV/bin/python" "$ODOO_DIR/odoo-bin" -d "$DB" --addons-path="$ADDONS"
