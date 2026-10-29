# SolarScope

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![Apache ECharts](https://img.shields.io/badge/ECharts-5.6-AA344D.svg)](https://echarts.apache.org/)
[![Local-First](https://img.shields.io/badge/Architecture-Local--First-success.svg)](#architecture)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SolarScope is an offline, local-first solar energy analytics platform. It transforms raw Excel (`.xlsx`, `.xlsm`) and CSV exports from residential and commercial solar inverters into accurate, explainable energy intelligence.

Designed for both everyday homeowners and solar engineering professionals, SolarScope provides a **Simple View** by default—communicating in plain language—alongside a **Detailed View** with complete physical formulas, mathematical proofs, and raw sensor channels.

---

## Key Features

- **Plain-Language Intelligence**: Everyday labels by default (*"Solar electricity produced"*, *"Electricity your home used"*, *"Electricity bought from TEI"*, *"Battery charge level"*), backed by an interactive **Help & Glossary** modal.
- **Dual-Perspective View Mode**: Instant toggle between **Simple View** (clean metrics and practical takeaways) and **Detailed View** (quadrature formulas, statistical definitions, and sensor boundary conditions).
- **Multi-File Batch Ingestion**: Upload dozens of single-day or multi-day exports at once. SHA-256 fingerprinting prevents double-counting, while conflict detection flags and resolves overlapping intervals.
- **Global Portfolio Aggregation**: Global Scope Selector applies across all 16 views simultaneously, switching seamlessly between **All Dates (Combined Portfolio)** and single-day deep dives.
- **Strict 12-Hour Clock Format**: Standardized `hh:mm AM/PM` formatting (`12 AM` to `11 PM`) across all timelines, hourly histograms, tooltips, anomaly logs, and generated audit reports.
- **Physical Energy Balance Reconciler**: Validates Kirchhoff bus conservation ($E_{residual} = E_{sources} - E_{sinks}$), decomposing residuals into continuous inverter tare load (~70 W), roundtrip conversion losses, and sensor polling skew.
- **"What If?" Upgrade Simulator**: Empirically tests hardware upgrades (larger battery pack, additional solar panels, minimum reserve adjustments, and daytime load shifting) using historical demand vectors.
- **Multi-Format Publication Reports**: Generates formal Engineering PDF audit reports (via ReportLab), multi-tab Excel workbooks (via OpenPyXL), and reproducible JSON packages.

---

## Architecture & Technology Stack

```
SolarScope Architecture
├── Frontend (Client)
│   ├── React 19 + TypeScript (Strict Mode)
│   ├── Vite 8 (Hot Module Replacement + API Reverse Proxy)
│   ├── Tailwind CSS + Custom Design System (Anti-AI-Slop compliance)
│   ├── Apache ECharts (Hardware-accelerated analytical charts)
│   └── Lucide SVG Icons (Zero emoji convention)
│
├── Backend (Analytics Engine)
│   ├── Python 3.12+ / FastAPI (Typed REST endpoints with Pydantic v2)
│   ├── Pandas, NumPy & SciPy (Time-differenced trapezoidal quadrature)
│   ├── OpenPyXL (Excel ingestion & multi-tab workbook builder)
│   ├── ReportLab (Vector graphics engineering PDF generator)
│   └── SQLite (Local metadata, provenance catalog & column mappings)
│
└── Storage Layer (Local-First)
    ├── SQLite Database (solarscope.db)
    └── Managed Local Directories (backend/data/uploads, backend/data/reports)
```

---

## Quick Start

### Prerequisites

- **Python 3.12+** (tested on Python 3.14)
- **Node.js 20+** (tested on Node v24 with npm 11)

### 1. Repository Installation

```powershell
git clone https://github.com/SODAAAH/SolarScope.git
cd SolarScope
```

#### Backend Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

#### Frontend Setup
```powershell
cd frontend
npm install
cd ..
```

### 2. Launch Development Environment

#### One-Click Windows Launchers
Run either launcher from the project root:
```cmd
start-dev.bat
```
or in PowerShell:
```powershell
.\start-dev.ps1
```

#### Manual Terminal Commands
**Terminal 1 — Backend API Server:**
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend Dev Server:**
```powershell
npm --prefix frontend run dev
```

- **Web Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Mathematical Methodology & Formulas

### 1. Timestamp-Differenced Trapezoidal Integration
Power measurements $P_i$ (kW) sampled at arbitrary non-uniform timestamps $t_i$:

$$\Delta t_i = t_{i+1} - t_i \quad \text{(seconds)}$$

$$E = \sum_{i=0}^{N-2} \left[ \frac{P_i + P_{i+1}}{2} \right] \cdot \frac{\Delta t_i}{3600} \quad \text{(kWh)}$$

Trapezoidal numerical integration accurately calculates energy across irregular intervals, missing sensor intervals, and communication gaps without assuming fixed 5-minute steps.

### 2. Energy Balance & Loss Reconciliation
At every point in time across the inverter DC/AC coupling nodes:

$$R(t) = P_{PV}(t) + P_{Batt}(t) + P_{Grid}(t) - P_{Load}(t)$$

Integrating over time yields the cumulative energy residual $E_{residual}$:

$$E_{residual} = E_{PV} + E_{Batt,disch} + E_{Grid,import} - E_{Load} - E_{Batt,chg} - E_{Grid,export}$$

In residential hybrid systems, this residual decomposes into:
1. **Continuous Inverter Standby / Tare Consumption**: ~70 W baseline (~1.68 kWh/day).
2. **Bidirectional Conversion Dissipation**: Thermal switching losses across DC-DC buck/boost and DC-AC inversion stages (~0.60 kWh/day).
3. **Sensor Polling Skew**: Asynchronous current transducer sampling (~0.22 kWh/day).

---

## Data Dictionary

| Original Column Header | Canonical Name | Unit | Sign Convention | Plain-Language Description |
| :--- | :--- | :--- | :--- | :--- |
| `Time` / `Timestamp` | `timestamp` | ISO-8601 | N/A | Observation timestamp with timezone awareness |
| `Production（kW）` | `pv_power_kw` | kW | Positive | Solar electricity produced (duplicate of `PV`) |
| `PV（kW）` | `pv_power_kw` | kW | Positive | DC photovoltaic array output power |
| `Consumption（kW）` | `load_power_kw` | kW | Positive | Total electricity your home used |
| `Grid（kW）` | `grid_power_kw` | kW | Positive = Import<br>Negative = Export | Electricity bought from TEI or pushed back |
| `Battery（kW）` | `battery_power_kw` | kW | Positive = Discharge<br>Negative = Charge | Electricity supplied by or stored into battery |
| `SOC（%）` | `soc_percent` | % | 0 - 100% | Battery charge level |
| `Generator（kW）` | `generator_power_kw` | kW | Positive | Auxiliary generator power (inactive channel) |
| `Grid-tied Inverter Power（kW）` | `grid_tied_inverter_power_kw` | kW | Positive | Secondary inverter power (inactive channel) |

---

## Verification & Audit Suites

Run the 20-test automated verification suite:
```powershell
python -m pytest backend/tests/ -v
```

Covered test suites:
- `test_12hour_formatting.py`: Validates 12-hour clock conversion across all 24 clock hours (`12 AM` to `11 PM`).
- `test_multifile_and_conflicts.py`: Validates SHA-256 fingerprinting, duplicate detection, and conflict policies.
- `test_historical_aggregation.py`: Verifies daily summaries, calendar rollups, and time-weighted averages.
- `test_api_endpoints.py`: End-to-end integration tests for health, sources, preview, and audit report generation.
- `test_integration.py`: Validates trapezoidal numerical integration over uniform and irregular intervals.
- `test_energy_balance.py`: Tests physical power conservation, zero-residual conditions, and self-consumption ratios.
- `test_ingestion_and_oct21.py`: Ingests benchmark `Oct 21.xlsx`, verifies identical duplicate channel detection (`Production` vs `PV`), and confirms dynamic integration benchmarks.

---

## Privacy, Security & Data Safety

- **100% Local-First**: Telemetry files and databases never leave your local machine.
- **Zero Cloud Databases**: No external cloud database or paid API keys required for core operations.
- **Safe Spreadsheet Processing**: Excel formula evaluation and macro execution are strictly disabled during ingestion.
- **Credential Protection**: Private energy records, database files, and local logs are excluded from source control.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
