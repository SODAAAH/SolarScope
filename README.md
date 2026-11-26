# SolarScope

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![Apache ECharts](https://img.shields.io/badge/ECharts-5.6-AA344D.svg)](https://echarts.apache.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SolarScope is a solar energy analytics, inverter telemetry, and TEI utility bill intelligence platform engineered for both local-first single-household operation and authenticated multi-household hosted deployment. It bridges live Deye Cloud monitoring with historical Excel/CSV telemetry ingestion to deliver energy attribution, battery cycle accounting, rate-schedule tracking, and empirical upgrade modeling.

---

## Core Engineering Features

- **Real-Time Deye Cloud Inverter Telemetry**: Bi-directional live flow monitoring (`eu` / `am` / `india` data centers) with 60-second cadence caching, missing-register detection, demo simulation safeguards, and multi-day historical range synchronization.
- **Origin-Attributed Energy Balance & Loss Accounting**: Physical interval reconciliation ($E_{residual} = E_{sources} - E_{sinks}$) separating solar-charged vs. grid-charged battery energy before computing solar self-consumption, solar self-sufficiency, conversion losses, and inverter standby tare.
- **Timezone-Aware Trapezoidal Integration**: Timestamp-differenced quadrature ($\Delta t_i = t_{i+1} - t_i$) supporting ISO 8601 offsets, UTC `Z`, naive installation-timezone strings, Excel serial datetimes, and Unix epoch timestamps without silent 1970 epoch fallback.
- **SOC-Compensated Battery Metrics**: Accounts for net stored energy change ($\Delta E_{batt}$) when computing closed-cycle and SOC-adjusted round-trip efficiency, equivalent full cycles, and estimated autonomy.
- **TEI Utility Tariff & Bill Intelligence**: Unbundled billing engine modeling Tarlac Electric Inc. (TEI) residential schedules, cycle date tracking, meter reading integration, and rate-sensitivity simulation with transparent estimated-vs-official labeling.
- **Multi-Household Isolation & Security**: Cookie + CSRF session authentication, strict `owner_user_id` -> `project_id` scoping across datasets/bills/configs/reports, and AES-256-GCM encryption at rest for Deye credentials.
- **Dual Storage Backends**: SQLite WAL mode for local-first desktops and managed PostgreSQL (`POSTGRES_URL` / `DATABASE_URL`) + Vercel Blob file storage for multi-instance serverless hosting.

---

## Architecture & Storage Modes

| Capability | Local-First Mode (`SOLARSCOPE_AUTH_REQUIRED=0`) | Hosted Multi-User Mode (`VERCEL=1` or `SOLARSCOPE_AUTH_REQUIRED=1`) |
| :--- | :--- | :--- |
| **Authentication** | Single-household automatic local profile (`default` project) | Required email/password authentication with HttpOnly session cookies + CSRF validation |
| **Project Isolation** | Supports multiple local installations cleanly scoped by `project_id` | Strict user ownership enforced on all datasets, uploads, Deye credentials, bills, and reports |
| **Database** | SQLite (`solarscope.db` in WAL mode) | Managed PostgreSQL (`POSTGRES_URL` or `DATABASE_URL`) with connection pooling & transactions |
| **Uploaded Files** | Local filesystem (`data/uploads`) + DB metadata | Vercel Blob (`BLOB_READ_WRITE_TOKEN`) + PostgreSQL `dataset_files` persistence fallback |
| **Secrets at Rest** | AES-256-GCM encrypted using `SOLARSCOPE_ENCRYPTION_KEY` or local `.solarscope.key` | Required `SOLARSCOPE_ENCRYPTION_KEY` environment variable (fails closed if unset in hosted mode) |
| **CORS** | Localhost Vite/FastAPI origins + `ALLOWED_ORIGINS` | Restricted strictly to explicit `ALLOWED_ORIGINS` (no wildcard deployment regex) |

---

## 10 Core Application Hubs

| Hub | Description |
| :--- | :--- |
| **Overview** | Live Deye power flow, daily generation/consumption rollups, Open-Meteo cloud forecast, billing/sync pulse strip, and first-time setup checklist. |
| **Solar Intelligence** | Array specific yield, clipping detection, Open-Meteo radiation/cloud correlation, and tomorrow solar generation forecast. |
| **Energy & Demand** | Origin-attributed household load coverage, SOC-adjusted battery round-trip efficiency, and grid import/export breakdown. |
| **Bill Intelligence** | TEI utility tariff audit, itemized Statement of Account preview, rate schedule archive, historical bill calibration, and sensitivity modeling. |
| **Trends & History** | Multi-day energy trends, weekday/weekend profiles, and statistical anomaly detection. |
| **Diagnostics** | Channel-level telemetry quality scoring (`MEASURED`, `CALCULATED`, `DEGRADED`, `UNAVAILABLE`), timestamp validation, and energy balance residuals. |
| **What-If & Upgrades** | Empirical battery/PV expansion simulator bounded by inverter and BMS limits with stated model assumptions. |
| **Energy Analyst** | Deterministic diagnostic Q&A engine plus real-time hardware health and system snapshot telemetry. |
| **Data Library & Cloud** | Pre-import inspection preview, batch Excel/CSV upload, conflict resolution, and encrypted Deye Cloud synchronization. |
| **System Settings** | PV module ratings, inverter/BMS limits, site coordinates/timezone, and per-installation electricity tariffs. |

---

## Environment Variables & Hosted Deployment

Copy `.env.example` to `.env.local` for local overrides (never commit `.env*` files containing real values):

- `POSTGRES_URL` / `DATABASE_URL`: PostgreSQL connection string for hosted multi-user deployment (defaults to local SQLite if unset).
- `SOLARSCOPE_AUTH_REQUIRED`: Set `1` in multi-user deployments to enforce authentication across all endpoints.
- `SOLARSCOPE_ENCRYPTION_KEY`: 32-byte URL-safe base64 key or passphrase used for AES-256-GCM credential encryption at rest (`python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`).
- `ALLOWED_ORIGINS`: Comma-separated production HTTPS origins allowed by CORS (e.g., `https://your-domain.vercel.app`).
- `BLOB_READ_WRITE_TOKEN`: Optional Vercel Blob token for cross-instance dataset file storage and daily SQLite backup snapshots when SQLite-on-Blob fallback is used.

---

## Quick Start (Local Development)

### Prerequisites

- **Python 3.12+**
- **Node.js 20+**

### Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

### Launch

```powershell
python dev.py
```

- **Web Dashboard**: `http://localhost:5173`
- **API Health**: `http://127.0.0.1:8000/api/health`

---

## Security & Safe Migrations

- Existing SQLite databases are migrated idempotently on startup (`init_db()`): legacy plaintext Deye `app_secret` and `password_encrypted` rows are re-encrypted automatically once an encryption key is configured.
- Uploaded spreadsheet bytes are stored safely with path traversal prevention, disabled macro execution, and SHA-256 per-project deduplication.
- API endpoints live strictly under `/api/*` without duplicate unprefixed route exposure.

---

## License

MIT License — see [LICENSE](LICENSE).
