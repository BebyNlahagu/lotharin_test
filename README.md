# Reseller Commission - Lotharin Screening Challenge (Part B)

Custom Odoo module for request 04 of the CV Mitra Karya Nusantara brief: monthly, tiered reseller commission.

* **Odoo version:** 18.0 Community, installed from source, PostgreSQL, Python virtualenv.
* **Tested on:** `<OS, e.g. Ubuntu 22.04 on WSL2>`, Python `<3.11.0>`, PostgreSQL `<17.0>`, Odoo commit `<hash from: git -C ~/odoo18 rev-parse HEAD>`.
* **Where resellers appear:** in the Contacts app the *Sales & Purchase* tab holds the **Is a Reseller** checkbox; a *Reseller* ribbon and a *Commissions* smart button show on flagged contacts; the *Resellers* filter is available in Contacts; and *Reseller Commission > Resellers* lists only resellers. The module depends on `contacts` so the app is always present.
* **Repository layout**

| Path                                               | Purpose                                                                                                                                                                                                                                 |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `addons/reseller_commission`                     | The single deliverable module: models, security, views, data, wizard, tests                                                                                                                                                             |
| `addons/reseller_commission/demo/`               | **Seed data only** (users, resellers, sample invoices). Loaded through the manifest `demo` key, so it exists only in databases created with demo data; kept apart from `data/`, which holds the configuration the client owns |
| `scripts/up_local.sh`, `scripts/test_local.sh` | Helper scripts wrapping the two commands of section 1                                                                                                                                                                                   |

## 1. Reproduction sequence (empty database -> working demo)

Ubuntu (or Ubuntu on WSL2). Every step is a command; nothing is configured by hand in the Odoo interface.

**1.1 System packages and PostgreSQL (once)**

```bash
sudo apt update
sudo apt install -y git python3-venv python3-dev build-essential libpq-dev \
  libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev libjpeg-dev zlib1g-dev \
  libssl-dev postgresql
sudo service postgresql start            # on plain Ubuntu: sudo systemctl start postgresql
sudo -u postgres createuser -s "$USER"   # database role = your Linux user
```

**1.2 Odoo 18 Community from source (once, Python 3.11 or newer)**

```bash
git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git "$HOME/odoo18"
python3 -m venv "$HOME/odoo18-venv"
"$HOME/odoo18-venv/bin/pip" install -r "$HOME/odoo18/requirements.txt"
```

**1.3 This repository**

```bash
git clone <this repository> lotharin-reseller-commission
cd lotharin-reseller-commission
```

**1.4 Install on an empty database and start Odoo**

```bash
dropdb --if-exists rc_demo               # guarantees an empty database
./scripts/up_local.sh                    # install module + seed, then start Odoo
```

`up_local.sh` runs exactly:

```bash
ADDONS="$HOME/odoo18/addons,$HOME/odoo18/odoo/addons,$(pwd)/addons"
$HOME/odoo18-venv/bin/python $HOME/odoo18/odoo-bin -d rc_demo --addons-path="$ADDONS" \
  -i reseller_commission --stop-after-init
$HOME/odoo18-venv/bin/python $HOME/odoo18/odoo-bin -d rc_demo --addons-path="$ADDONS"
```

The seed data in `demo/` is installed because a new database is created with Odoo's demo mode on (the default); Odoo's own demo data is loaded as well, which does not interfere because only partners flagged as resellers earn commission. A production database is created with `--without-demo=all`, so no seed data is ever installed there.

If Odoo or the virtualenv live elsewhere, set `ODOO_DIR`, `VENV` and/or `DB` before running the script.

Then open http://localhost:8069, database `rc_demo`. Logins (password = login):

| Login                          | Role                   | Can                                           |
| ------------------------------ | ---------------------- | --------------------------------------------- |
| `admin` / `admin`          | Administrator          | everything                                    |
| `sales_andi`, `sales_budi` | Commission Salesperson | view commissions of their own resellers only  |
| `cm_manager`                 | Commission Manager     | see all, generate, confirm, reset, edit tiers |
| `cm_accounting`              | Commission Accounting  | see all, mark confirmed records as paid       |

**1.5 Exercise the flow**

1. Log in as `cm_manager` -> *Reseller Commission > Generate Commissions* -> keep the default month (last month) -> Generate.
   Expected (seed data): Toko Mebel Andalas 40,000,000 -> 3% = 1,200,000 / CV Bangun Interior 120,000,000 -> 5% = 6,000,000 / PT Griya Kontraktor 180,000,000 - 10,000,000 refund = 170,000,000 -> 7% = 11,900,000.
   The ordinary customer and the unposted invoice are ignored.
2. Open a record: the *Source Documents* tab lists the invoices. *Confirm* it. Fields are now locked.
3. Log in as `cm_accounting` -> open it -> *Mark as Paid*.
4. Log in as `sales_andi`: only Andalas and Griya are visible, no action buttons.
5. *Commission Summary* shows the pivot/graph across resellers and months (generate the month before as well to fill it; PT Griya's earlier month is exactly Rp 50,000,000 to show the tier boundary).

**1.6 Idempotency and automated tests**

Upgrade run, must not duplicate or break anything (tiers, users, invoices, commissions stay as they are):

```bash
$HOME/odoo18-venv/bin/python $HOME/odoo18/odoo-bin -d rc_demo \
  --addons-path="$HOME/odoo18/addons,$HOME/odoo18/odoo/addons,$(pwd)/addons" \
  -u reseller_commission --stop-after-init
```

Automated tests (bonus, throwaway database `rc_test`, dropped first): `./scripts/test_local.sh`

## 2. Functional decisions and assumptions

* **Calculation basis: posted customer invoices** (`out_invoice` minus `out_refund`, state *posted*, by invoice date), amount **excluding tax**, in company currency.
  Why not confirmed sale orders: an order can be cancelled, partly delivered or invoiced in several steps (made-to-order furniture is typically invoiced with a down payment), and the accountant closes the month on invoices, so commission and books agree. VAT (PPN) is not revenue of the client, so it is excluded. Credit notes reduce the month in which they are posted.
* **Tier rate applies to the whole monthly total** (not marginally): 120 M -> 5% on all 120 M. The brief says "based on their total sales".
* **Boundaries:** a tier's lower bound is inclusive; exactly Rp 150,000,000 therefore earns 7%, exactly Rp 50,000,000 earns 5%. The brief is ambiguous at 150 M ("150 million" vs "above 150 million"); the client can set the bound to 150,000,001 in the UI.
* A net-negative month (refunds exceed sales) yields commission 0, no clawback carried to the next month.
* The reseller is the **commercial entity** (company); invoices of its contacts roll up to it. The flag cannot be set on a child contact and cannot be removed once commissions exist.
* "Salesperson sees only their own resellers" = the partner's standard *Salesperson* field (`user_id`); record rules restrict commissions, lines **and the reseller contacts themselves** to it (managers and accounting see all). Non-reseller contacts are not affected.
* "Paid the following month": the record holds a *Payable From* date (first day of the next month). The actual payment is the manual *Mark as Paid*.
* No commission record is created for a reseller with no invoices in the month.

## 3. Model design

* `res.partner` (inherited): `is_reseller` flag + constraints.
* `reseller.commission.tier`: `min_amount` (inclusive lower bound) + `rate`. A reseller falls in the highest tier whose bound is <= their total. Lower bounds only, so tiers can never overlap or leave gaps. `unique(company, min_amount)`, `min >= 0`, `0 <= rate <= 100` are declarative constraints.
* `reseller.commission`: one per reseller + month + company (unique constraint). `total_sales` and `commission_amount` are stored computed fields with correct `@api.depends`; `rate`/`tier_id` are a **snapshot** at calculation time so later tier changes never alter an already calculated record (use *Recompute* on a draft to refresh). Chatter tracks status and amount.
* `reseller.commission.line`: link to the source `account.move` + the net amount at calculation time.
* `reseller.commission.generate.wizard`: manual generation for a month (all or selected resellers).
* **Workflow & locks** (enforced in `write/create/unlink`, not only in the UI): draft -> confirmed (manager), confirmed -> draft (manager), confirmed -> paid (accounting). Business fields and lines are locked outside draft, only draft records can be deleted, and *Confirm* refuses if the invoices changed since the calculation (asks for *Recompute*).
* **Generation is idempotent**: confirmed/paid records are skipped, drafts are recalculated, drafts that no longer have sales are removed. The scheduled action (monthly, previous month, every company) and the wizard share the same method.

### Access matrix

|                    | Salesperson              | Manager   | Accounting                       |
| ------------------ | ------------------------ | --------- | -------------------------------- |
| Commission / lines | read, own resellers only | CRUD, all | read + write (to mark paid), all |
| Tiers              | read                     | CRUD      | no access via menu               |
| Confirm / reset    | no                       | yes       | no                               |
| Mark paid          | no                       | no        | yes                              |

Rules: multi-company on all three models; salesperson rule on `reseller_id.user_id`; manager/accounting see all. `base.group_system` implies the manager and accounting groups so the administrator works out of the box.

## 4. Configuration as code: what is owned by whom

| Data                                             | File                                       | `noupdate`                                                                          | Reason                                                                                   |
| ------------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Groups, ACLs, record rules, views, menus, wizard | `security/`, `views/`, `wizard/`     | no (refreshed on every upgrade)                                                       | Developer-owned; a fix must reach every environment                                      |
| Commission tiers                                 | `data/reseller_commission_tier_data.xml` | **yes**                                                                         | The client edits rates in the UI; an upgrade must not overwrite them                     |
| Sequence                                         | `data/ir_sequence_data.xml`              | **yes**                                                                         | Prefix/padding/next number are client-owned                                              |
| Monthly cron                                     | `data/ir_cron_data.xml`                  | **yes**                                                                         | Client may change schedule or switch it off                                              |
| Users, resellers, sample invoices                | `demo/` (manifest `demo` key)          | users/partners yes; invoices via an idempotent loader keyed on the customer reference | Seed only: installed solely in demo-mode databases, separate from client-owned `data/` |

All references use XML ids, no database ids anywhere. User-facing strings use `_()` / field labels and are translatable.

**Not expressible as code** (explicitly manual in a real deployment): installing Odoo and PostgreSQL on the server, creating the production database (with `--without-demo=all`) and admin password, the client's real chart of accounts/fiscal localisation (the seed loads the generic chart only so invoices can be posted), assigning real staff to the commission groups, and real reseller master data. The seed data shows how those would look.

**Raw SQL:** none. Only declarative `_sql_constraints`.
**`sudo()`:** used in one place, reading invoices to calculate commission (`_search_source_moves`), because the commission manager is not required to hold accounting rights; the feature itself is gated by the commission groups. The demo loader and `Recompute` go through the same method.

## 5. Trade-offs and what I would do with more time

* Whole-total tiers are simple and transparent but create a cliff at each bound; a marginal-rate mode could be a tier-set option.
* Commission is by invoice date, not by payment: a reseller who has not paid still earns commission. A "paid invoices only" mode (or a clawback on unpaid invoices) is the first thing to confirm with the client.
* No outgoing email on confirmation/payment (not required); a mail template + notification to the reseller's salesperson would be next.
* Payment is a status only; generating the vendor bill / payment in accounting would close the loop.
* Uninstall: the module removes its own records cleanly, but the sample invoices of the seed data are posted accounting entries, which Odoo does not allow to be deleted; they remain (and a demo database is meant to be discarded, not uninstalled).
* Odoo is cloned from the moving `18.0` branch, so the exact Odoo commit tested is recorded in the header; a pinned commit or a container image would make the environment stricter.
* Add Indonesian `.po` translation, a REST endpoint for the commission summary, and a wider test matrix (multi-company, multi-currency invoices).

## 6. Verification

* Environment: `<OS>`, Python `<x.y.z>`, PostgreSQL `<x>`, Odoo 18.0 commit `<hash>`.
* Fresh-database install (`./scripts/up_local.sh`): `<passed / notes>`.
* Automated tests (`./scripts/test_local.sh`): `<N tests, all passed / notes>`.
* Known limitations: `<list, or "none known">`.

## 7. AI assistance disclosure

I used Claude (Anthropic) to draft the module code and automated tests, the seed data, the helper scripts, this README and the Part A solution document, and to explain the setup steps. After that I `<describe what you did yourself: ran it on a clean database, fixed ..., changed ..., verified ...>`. I can explain and modify every part of the code live.

## 8. Other deliverables

* Solution document (Part A, PDF): `<link or docs/ path>`
* Demo recording (5-8 min): `<link>`
* Approximate hours spent: `<n>`
