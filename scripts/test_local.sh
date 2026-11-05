#!/usr/bin/env bash
# Runs the automated tests of reseller_commission on a throwaway database (dropped first).
set -euo pipefail
cd "$(dirname "$0")/.."
ODOO_DIR="${ODOO_DIR:-$HOME/odoo18}"
VENV="${VENV:-$HOME/odoo18-venv}"
DB="${DB:-rc_test}"
ADDONS="$ODOO_DIR/addons,$ODOO_DIR/odoo/addons,$(pwd)/addons"
dropdb --if-exists "$DB"
"$VENV/bin/python" "$ODOO_DIR/odoo-bin" -d "$DB" --addons-path="$ADDONS" -i reseller_commission \
  --test-enable --test-tags /reseller_commission --without-demo=all --stop-after-init
