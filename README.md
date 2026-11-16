# InvoisLah 🌿 — Python edition

A redesigned, **Python-first Streamlit** replacement for the supplied React/TypeScript Lovable prototype. Soft lime green (`#ADD47E`) is based on the supplied reference image; dark evergreen provides readable text and button contrast.

## Running the app (Windows / macOS / Linux)

Python 3.10 or newer is recommended.

```bash
cd InvoisLah_Python
python -m venv .venv
```

Activate the environment:

- **Windows PowerShell:** `.venv\Scripts\Activate.ps1`
- **Windows CMD:** `.venv\Scripts\activate.bat`
- **macOS/Linux:** `source .venv/bin/activate`

Install and start:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit usually opens `http://localhost:8501` automatically. Camera access works with permission on localhost or HTTPS (phone camera support varies by browser). To open from another device, use a secure HTTPS deployment rather than exposing this unauthenticated prototype to the public internet.

## What changed from your original React app

| Original | Python edition |
| --- | --- |
| React / TypeScript, repeated create/edit form logic | Streamlit + shared Python modules and a single reusable create/edit form |
| Orange and blue/purple visual design | Consistent lime-green and forest-green UI |
| Dashboard sample totals and dated 2024 mock invoices | Live totals calculated from actual saved records; clear empty state |
| Supabase anonymous read/write/delete policies | Local SQLite database; no publicly exposed anonymous database |
| Invoice PDF and duplicate buttons only showed toast messages | Working ReportLab PDF download and actual duplicate-draft operation |
| PDF template implicitly used 6% tax / RM | Configurable line-level tax code and rate; currency-aware formatting |
| One broad payment status | Separate local payment status and `NOT_SUBMITTED` LHDN status |
| Outdated RM150k compliance claim | Updated LHDN guidance and links with limitations |
| No receipt inbox/camera workflow | Upload **beside** camera capture, preview, optional invoice linking, storage and download |

### Features

- Real dashboard counts, MYR-equivalent paid revenue (using user-entered FX rates), overdue tracking and recent invoices.
- Create, edit, duplicate, filter, change local payment status, delete, export CSV and generate invoice PDF.
- Multi-row invoice lines with quantity, unit price, classification and tax type/rate; discounts, extra charges and Decimal arithmetic.
- Business profile (TIN, ID type, MSIC, registration, address, telephone), optional business logo upload or photo, and buyer identity fields.
- Receipt/document inbox with `st.file_uploader` and `st.camera_input` **next to each other** (also available side by side for business-logo capture in Settings); JPEG/PNG/PDF support, 10 MB max, optional link to an invoice, and local downloads.
- A compliance hub with original LHDN links and explicit distinction between locally created documents and **MyInvois-validated** e-Invoices.

### Files

- `app.py` — navigation and UI
- `style.py` — shared visual tokens and CSS
- `data_store.py` — one SQLite storage layer, atomic transactions, receipt storage
- `invoice_logic.py` — one calculation and field-checking layer
- `pdf_export.py` — downloadable PDF rendering
- `.streamlit/config.toml` — theme configuration
- `tests/test_core.py` — automated checks for calculation, DB, validation, PDF, and attachments

Run tests from the project directory:

```bash
python -m pytest -q
```

### Local data & migration

Data is created only when the app runs under `data/invoislah.db` and `data/uploads/`. It is excluded from Git. Override with `INVOISLAH_DATA_DIR` (environment variable). **Data from the original Supabase project is NOT automatically migrated**, because no authenticated data export or migration credentials were provided. Export old invoice data separately before retiring the original application. No Supabase keys or original `.env` have been copied into this project.

## LHDN policy review (checked 16 November 2026)

- The official [implementation timeline](https://www.hasil.gov.my/en/e-invois/pelaksanaan-e-invois-di-malaysia/garis-masa-pelaksanaan-e-invois/) was updated 30 August 2026. It now says taxpayers with annual turnover/revenue **less than RM3 million** are exempt from e-Invoice implementation; this is subject to full eligibility conditions and detailed exceptions. Phase dates include 1 January 2026 for the `≤ RM5 million` tier subject to the exemption.
- The official [e-Invoice Guideline v4.8 and Specific Guideline v4.9](https://www.hasil.gov.my/en/e-invois/rujukan-pelaksanaan-e-invois/garis-panduan/) were published 30 August and 7 September 2026 respectively.
- MyInvois [tax type codes](https://sdk.myinvois.hasil.gov.my/codes/tax-types/) are 01–06 and E; applicability and rate vary by transaction. This app does **not** assign one universal 6% or 8% rate.
- [Classification codes](https://sdk.myinvois.hasil.gov.my/codes/classification-codes/) apply at line-item level. The form starts with **022 – Others**, but the issuer must check that the code is applicable.
- The full [SDK validation](https://sdk.myinvois.hasil.gov.my/document-validation-rules/) involves structural, digital signature, taxpayer, duplicate, currency and code checks, among others.
- The SDK [cancellation documentation](https://sdk.myinvois.hasil.gov.my/einvoicingapi/03-cancel-document/) describes a 72-hour window after validation for cancellation. After that, corrections may require credit/debit/refund notes.

### What is **not** implemented / not ready for production

**Important:** This is still an invoice management **prototype**. It **does not** issue, authenticate, sign, submit, validate, cancel, or query documents through the official MyInvois system. All generated PDFs are plainly labelled **NOT VALIDATED** and have no fabricated LHDN QR, UUID or submission acknowledgement. **Preliminary local form checks are not certification of legal compliance.**

Other gaps before commercial use: official complete UBL 2.1 JSON/XML mapping, up-to-date SDK code table validators, correct tax/discount/charge allocation per document type, official taxpayer validation, credit/debit/refund/self-billed/consolidated workflows, regulatory retention policy, audit logging, authentication, access controls, backups, encryption at rest, and business-specific SST advice. Extra charges are **not automatically taxed** (issuer must review). Invoices in non-MYR currencies rely on a user-entered MYR exchange rate for dashboard totals. User-entered TINs and IDs are **not verified** with LHDN. Receipt image capture does **not** perform OCR.

The original Supabase project included policies permitting public CRUD access without per-user authentication; the new local architecture avoids making this database remotely available, **but it is not safe to deploy publicly as-is**.

## Development / testing notes

Recommended Python: 3.11+. The React, TypeScript, npm lockfiles, generated UI components, unused toast-only handlers, and Supabase migration are intentionally not included in the Python deliverable because this is a standalone rebuild, **not** a drop-in conversion preserving the original Supabase service or pixel-exact React UI.
