
# Reseller Commission - Odoo 18

Custom Odoo module for the Lotharin screening challenge, Part B (request 04 of the CV Mitra Karya Nusantara brief): **monthly, tiered commission for resellers**, calculated from posted customer invoices, with a draft / confirmed / paid workflow and role-based access.

Requests 01-03 and 05-06 of the brief are analysed in the Part A solution document (see section 8); only request 04 is built here.

## 0. At a glance

* **Odoo version:** 18.0 Community, installed from source, no Docker.
* **Tested on:** `<windows>`, Python `<3.11>`, PostgreSQL `<18.0>`, Odoo commit `<ac43dda46c08>`.
* **Module:** `addons/reseller_commission` (single module; depends on `account`, `contacts`, `mail`).
* **Seed data:** `addons/reseller_commission/demo/`, loaded only in databases created with demo data. Client-owned configuration lives in `data/`.
* **Where resellers appear:** a contact flagged *Is a Reseller* (tab *Sales & Purchase*) shows a *Reseller* ribbon and a *Commissions* smart button; *Contacts* has a *Resellers* filter; *Reseller Commission > Resellers* lists only resellers.

## 1. Reproduction sequence (empty database -> working demo)

Windows (PowerShell). Every step is a command; nothing is configured by hand in the Odoo interface. Adjust the paths and database credentials to your machine.

**1.1 Prerequisites (once):** Git, Python 3.10 or newer, and a running PostgreSQL server with a role that may create databases (`psql`/`dropdb` on the PATH).

**1.2 Odoo 18 source and virtual environment (once)**

```powershell
git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git E:\odoo18\odoo
python -m venv E:\odoo18\venv
E:\odoo18\venv\Scripts\pip install -r E:\odoo18\odoo\requirements.txt
```

**1.3 This repository**

```powershell
git clone https://github.com/BebyNlahagu/lotharin_test.git E:\odoo18\lotharin-reseller-commission
```

Make sure the folder `reseller_commission` exists **only once** in the addons path; a stale copy elsewhere is loaded instead of this one.

**1.4 Variables used below**

```powershell
$ODOO   = "E:\odoo18\odoo"
$PY     = "E:\odoo18\venv\Scripts\python.exe"
$ADDONS = "$ODOO\addons,$ODOO\odoo\addons,E:\odoo18\lotharin-reseller-commission\addons"
$DB     = @("--db_host=localhost", "--db_user=<pg user>", "--db_password=<pg password>")
```

**1.5 Install on an empty database, then run**

```powershell
$env:PGPASSWORD = "<pg password>"
dropdb -h localhost -U <pg user> --if-exists rc_demo        # guarantees an empty database

& $PY "$ODOO\odoo-bin" -d rc_demo --addons-path=$ADDONS @DB -i reseller_commission --stop-after-init
& $PY "$ODOO\odoo-bin" -d rc_demo --addons-path=$ADDONS @DB
```

Open http://localhost:8069, database `rc_demo`.

The seed data in `demo/` is installed because a new database is created with Odoo's demo mode on (the default). Odoo's own demo data is loaded as well; it does not interfere, because only partners flagged as resellers earn commission. A production database is created with `--without-demo=all`, so no seed data is ever installed there.

Logins (password = login):

| Login                          | Role                   | Can                                                                |
| ------------------------------ | ---------------------- | ------------------------------------------------------------------ |
| `admin` / `admin`          | Administrator          | everything                                                         |
| `sales_andi`, `sales_budi` | Commission Salesperson | view commissions and reseller contacts of their own resellers only |
| `cm_manager`                 | Commission Manager     | see all, generate / recompute, confirm, reset, edit tiers          |
| `cm_accounting`              | Commission Accounting  | see all, generate / recompute, mark confirmed records as paid      |

**1.6 Exercise the flow**

1. Log in as `cm_manager` (or `cm_accounting`) -> *Reseller Commission > Generate Commissions* -> keep the default month (last month) -> Generate.
   Expected with the seed data: Toko Mebel Andalas 40,000,000 -> 3% = 1,200,000 / CV Bangun Interior 120,000,000 -> 5% = 6,000,000 / PT Griya Kontraktor 180,000,000 - 10,000,000 credit note = 170,000,000 -> 7% = 11,900,000.
   Ignored on purpose: the ordinary customer (not a reseller) and the unposted draft invoice of Bangun (30,000,000).
2. As `cm_manager`, open a record: the *Source Documents* tab lists the invoices. *Confirm* it. Business fields are now locked.
3. Log in as `cm_accounting` -> open it -> *Mark as Paid*.
4. Log in as `sales_andi`: only Andalas and Griya are visible, and there are no action buttons.
5. *Commission Summary* shows the pivot / graph across resellers and months. Generate the month before as well to fill it; PT Griya's earlier month is exactly Rp 50,000,000 to show the tier boundary.

**1.7 Idempotency check and automated tests**

Upgrade run; tiers, users, invoices and commissions must stay as they are, with no duplicates:

```powershell
& $PY "$ODOO\odoo-bin" -d rc_demo --addons-path=$ADDONS @DB -u reseller_commission --stop-after-init
```

Automated tests on a throwaway database:

```powershell
dropdb -h localhost -U <pg user> --if-exists rc_test
& $PY "$ODOO\odoo-bin" -d rc_test --addons-path=$ADDONS @DB -i reseller_commission `
  --test-enable --test-tags /reseller_commission --without-demo=all --stop-after-init
```

## 2. Functional decisions and assumptions

Where the brief is silent I decided, and wrote the assumption here.

* **Calculation basis: posted customer invoices** (`out_invoice` minus `out_refund`, state *posted*, by invoice date), amount **excluding tax**, in company currency.
  Why not confirmed sale orders: an order can be cancelled, partly delivered or invoiced in several steps (made-to-order furniture is typically invoiced with a down payment), and the accountant closes the month on invoices, so commission and books agree. VAT (PPN) is not revenue of the client, so it is excluded. Credit notes reduce the month in which they are posted.
* **Tier rate applies to the whole monthly total** (not marginally): 120 M -> 5% on all 120 M. The brief says "based on their total sales".
* **Boundaries:** a tier's lower bound is inclusive, so exactly Rp 150,000,000 earns 7% and exactly Rp 50,000,000 earns 5%. The brief is ambiguous at 150 M ("150 million" vs "above 150 million"); the client can set that bound to 150,000,001 in the UI.
* A net-negative month (credit notes exceed sales) yields commission 0; nothing is carried to the next month.
* **Reseller = commercial entity** (company); invoices of its contacts roll up to it. The flag cannot be set on a child contact, and cannot be removed once commissions exist.
* **Who generates:** the brief does not say. The monthly scheduled action generates automatically; managers and accounting can also generate or recompute manually (drafts only). As the brief states, only managers confirm and only accounting marks records as paid.
* **Who posts the invoices:** outside this module. Finance staff with the standard Odoo *Invoicing* right create and post customer invoices; salespeople and the commission groups cannot. Only posted invoices count, so the month's invoices should be posted before commissions are confirmed (*Confirm* refuses if the invoices changed since the calculation and asks for *Recompute*).
* **"A salesperson may view only their own resellers"** is implemented with the partner's standard *Salesperson* field (`user_id`): record rules restrict commissions, their lines and the reseller contacts themselves to it. Managers and accounting see all. Non-reseller contacts are not affected.
* **"Paid the following month":** each record holds a *Payable From* date (first day of the next month). The payment itself is the manual *Mark as Paid* by accounting.
* No commission record is created for a reseller with no invoices in the month.

## 3. Model design

* `res.partner` (inherited): `is_reseller` flag, constraints, and a *Commissions* smart button (count computed with a single grouped query).
* `reseller.commission.tier`: `min_amount` (inclusive lower bound) + `rate`. A reseller falls in the highest tier whose bound is <= their total. Lower bounds only, so tiers can never overlap or leave gaps. `unique(company, min_amount)`, `min >= 0` and `0 <= rate <= 100` are declarative constraints. Tiers are data, editable in the UI.
* `reseller.commission`: one per reseller + month + company (unique constraint). `total_sales` and `commission_amount` are stored computed fields with their `@api.depends`. `rate` and `tier_id` are a **snapshot** taken at calculation time, so later tier changes never alter a calculated record (use *Recompute* on a draft to refresh). Chatter tracks status and amount.
* `reseller.commission.line`: link to the source `account.move` + the net amount at calculation time.
* `reseller.commission.generate.wizard`: manual generation for a month (all or selected resellers).
* **Workflow and locks** (enforced in `write` / `create` / `unlink`, not only in the UI): draft -> confirmed (manager), confirmed -> draft (manager), confirmed -> paid (accounting). Paid is final. Business fields and lines are locked outside draft, and only drafts can be deleted.
* **Generation is idempotent:** confirmed and paid records are skipped, drafts are recalculated, drafts that no longer have sales are removed. The monthly scheduled action (previous month, every company) and the wizard call the same method.

### Access matrix

|                               | Salesperson              | Manager                            | Accounting                         |
| ----------------------------- | ------------------------ | ---------------------------------- | ---------------------------------- |
| Commissions and lines         | read, own resellers only | create / edit / delete drafts, all | create / edit / delete drafts, all |
| Reseller contacts             | own resellers only       | all                                | all                                |
| Tiers                         | read                     | create / edit / delete             | read                               |
| Generate / recompute (drafts) | no                       | yes                                | yes                                |
| Confirm / reset to draft      | no                       | yes                                | no                                 |
| Mark as paid                  | no                       | no                                 | yes                                |

Rules: multi-company on the three models; a salesperson rule on `reseller_id.user_id` (commissions, lines, reseller contacts); manager and accounting rules that see all. `base.group_system` implies the manager and accounting groups, so the administrator works out of the box. Anyone who can edit a contact can tick *Is a Reseller* (see section 5).

## 4. Configuration as code: who owns what

| Data                                             | File                                       | `noupdate`                                                                                  | Reason                                                                                   |
| ------------------------------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Groups, ACLs, record rules, views, menus, wizard | `security/`, `views/`, `wizard/`     | no (refreshed on every upgrade)                                                               | Developer-owned; a fix must reach every environment                                      |
| Commission tiers                                 | `data/reseller_commission_tier_data.xml` | **yes**                                                                                 | The client edits rates in the UI; an upgrade must not overwrite them                     |
| Sequence                                         | `data/ir_sequence_data.xml`              | **yes**                                                                                 | Prefix, padding and next number are client-owned                                         |
| Monthly scheduled action                         | `data/ir_cron_data.xml`                  | **yes**                                                                                 | The client may change the schedule or switch it off                                      |
| Users, resellers, sample invoices                | `demo/` (manifest `demo` key)          | users and partners yes; invoices through an idempotent loader keyed on the customer reference | Seed only: installed solely in demo-mode databases, separate from client-owned `data/` |

All references use XML ids, never database ids. User-facing strings use `_()` or field labels and are translatable.

**Not expressible as code** (manual in a real deployment): installing Odoo and PostgreSQL, creating the production database (with `--without-demo=all`) and the admin password, the client's real chart of accounts and tax localisation, assigning real staff to the commission groups and to the Odoo *Invoicing* right, and the real reseller master data. The seed data shows how those would look.

**Raw SQL:** none, only declarative `_sql_constraints`.
**`sudo()`:** used in two places, both read-only checks: reading invoices to calculate commission (`_search_source_moves`, because the commission manager need not hold accounting rights; the feature itself is gated by the commission groups), and the "flag in use" check on the partner.

## 5. Trade-offs, known limitations and next steps

Trade-offs accepted:

* Whole-total tiers are simple and transparent but create a cliff at each bound; a marginal-rate mode could be a tier-set option.
* Commission follows the invoice date, not the payment: a reseller who has not paid still earns commission. A "paid invoices only" mode (or a clawback) is the first thing to confirm with the client.

Known limitations:

* Anyone who can edit a contact can tick *Is a Reseller*; restricting that field to the commission manager group is the obvious follow-up.
* The seed data's sample invoices are posted accounting entries, which Odoo does not let anyone delete; they remain if the module is uninstalled (a demo database is meant to be discarded).
* The commission count on the contact is computed with a grouped query and not stored, so it is recomputed every time a contact is opened.
* Odoo is cloned from the moving `18.0` branch; the commit tested is recorded in section 0.

With more time:

* Email notification to the salesperson on confirmation and payment, using a mail template.
* Generate the vendor bill or payment in accounting when a record is marked paid..

## 6. Verification

* Environment: `<windows>`, Python `<3.11>`, PostgreSQL `<18.0>`, Odoo 18.0 commit `<ac43dda46c08>`.
* Fresh-database install (section 1.5): `<passed / notes>`.
* Idempotent upgrade (section 1.7): `<passed / notes>`.
* Automated tests (section 1.7): `<N tests, all passed / notes>`.
* Flow of section 1.6 with the four logins: `<passed / notes>`.

## 7. AI assistance disclosure

I used two AI tools:

* **ChatGPT Codex (OpenAI):** to help with the requirement analysis (understanding the six client requests and deciding what to configure, customise or change in the process).
* **Claude (Anthropic):** to draft the module code and the automated tests, the seed data, this README and the Part A solution document, and to explain the setup steps.

After that I wrote code, tested the module and fixed the problems I found while testing. I can explain and modify every part of the code live.

## 8. Other deliverables

* Solution document (Part A, PDF): `<\..\docs\Lotharin_Bagian_A_Solution_Design_Draft.pdf>`
* Demo recording (5-8 min): `<link>`
* Approximate hours spent: `<n>`
