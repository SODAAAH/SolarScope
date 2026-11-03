# SolarScope

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![Apache ECharts](https://img.shields.io/badge/ECharts-5.6-AA344D.svg)](https://echarts.apache.org/)
[![Local-First](https://img.shields.io/badge/Architecture-Local--First-success.svg)](#architecture--technology-stack)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SolarScope is an offline, local-first solar energy analytics and telemetry platform. It bridges live Deye Cloud inverter monitoring with historical multi-file telemetry ingestion to deliver rigorous physical loss accounting, utility tariff intelligence, and empirical hardware simulation.

---

## Core Engineering Features

- **Real-Time Deye Cloud Inverter Telemetry**: Live bi-directional integration streaming instantaneous bus power flows (PV, Battery, Grid, Load, SOC) with animated flow vectors and automated gap backfilling.
- **Physical Energy Balance & Loss Accounting**: First-principles physical loss reconciliation across DC/AC coupling nodes ($E_{residual} = E_{sources} - E_{sinks}$), decomposing residuals into continuous inverter tare load (~70 W), bidirectional conversion losses, and current transducer sampling skew.
- **Timestamp-Differenced Trapezoidal Quadrature**: Numerical integration across arbitrary, non-uniform sensor timestamps ($\Delta t_i = t_{i+1} - t_i$) that computes true cumulative energy (kWh) without naive fixed-step assumptions.
- **TEI Utility Tariff & Bill Intelligence**: Precision billing engine modeling Tarlac Electric Inc. (TEI) rate structures, multi-tier energy pricing, peak demand charges, and billing period cost forecasting.
- **Empirical Hardware Upgrade Simulation**: High-resolution "What-If" simulator evaluating physical system expansions (battery capacity, additional PV string capacity, reserve SOC tuning, daytime load shifting) against historical load vectors.
- **Multi-File Batch Ingestion & Conflict Engine**: Multi-source spreadsheet (`.xlsx`, `.xlsm`) and CSV ingestion engine with SHA-256 fingerprinting for deduplication and automated policy-driven overlap resolution.
- **Fast-Path Diagnostic Intelligence**: Deterministic query engine providing instantaneous technical evaluations backed by verified physical telemetry benchmarks.

---

## Architecture & Technology Stack

```
SolarScope Architecture
├── Frontend (Client)
│   ├── React 19 + TypeScript (Strict Mode)
│   ├── Vite 8 (Hot Module Replacement + Dev Reverse Proxy)
│   ├── Tailwind CSS + Custom Design System (Zero emoji, clean UI)
│   ├── Apache ECharts (Hardware-accelerated analytical visualizations)
│   └── Lucide SVG Icons (Professional glyph convention)
│
├── Backend (Analytics Engine)
│   ├── Python 3.12+ / FastAPI (Typed REST endpoints with Pydantic v2)
│   ├── Pandas, NumPy & SciPy (Timestamp-differenced trapezoidal quadrature)
│   ├── OpenPyXL (Excel ingestion & multi-tab workbook processing)
│   ├── ReportLab (Vector graphics engineering audit export)
│   └── SQLite (Local metadata catalog, provenances, and tariff schedules)
│
├── Process Supervisor
│   └── dev.py (Single-window lifecycle manager with automated port clearing & Ctrl+C cleanup)
│
└── Storage Layer (Local-First)
    ├── SQLite Database (solarscope.db)
    └── Managed Local Directories (backend/data/uploads, backend/data/reports)
```

---

## 10 Core Application Hubs

| Hub | Description |
| :--- | :--- |
| **Overview** | Real-time animated power flow, 24-hour diurnal power profile with date switcher, live summary, and monthly generation/consumption bars. |
| **Solar Intelligence** | Photovoltaic array performance, peak sun hours, clipping detection, string efficiency, and diurnal solar curves. |
| **Energy & Demand** | Total home consumption, base vs. peak load decomposition, and diurnal demand histograms. |
| **Bill Intelligence** | TEI utility billing audit, monthly tariff breakdown, demand charges, and billing period progress tracking. |
| **Trends & History** | Long-term energy generation and consumption trends with multi-day calendar rollups. |
| **Diagnostics** | Physical residual breakdown, continuous inverter standby tare (~70 W), conversion efficiency, and telemetry quality scoring. |
| **What-If & Upgrades** | Empirical hardware simulation for battery pack expansion, additional PV modules, and daytime load shifting. |
| **Energy Analyst** | Fast-path diagnostic intelligence engine providing instant operational answers backed by observed energy metrics. |
| **Data Library & Cloud** | Historical spreadsheet file management, Deye Cloud live synchronization, and conflict resolution. |
| **System Settings** | Manual system parameters, utility tariff schedules, inverter hardware ratings, and local cloud credentials. |

---

## Quick Start

### Prerequisites

- **Python 3.12+** (tested on Python 3.12 to 3.14)
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

Run the unified single-window launcher from the project root. This starts both the FastAPI backend and Vite frontend inside a single terminal session, automatically clears occupied ports, and cleanly shuts down both processes on `Ctrl+C`:

#### Windows Command Prompt:
```cmd
start-dev.bat
```

#### PowerShell:
```powershell
.\start-dev.ps1
```

#### Or Directly via Python:
```powershell
python dev.py
```

- **Web Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Mathematical Methodology & Formulas

### 1. Timestamp-Differenced Trapezoidal Integration
Power measurements $P_i$ (kW) sampled at arbitrary non-uniform timestamps $t_i$:

$$\Delta t_i = t_{i+1} - t_i \quad \text{(seconds)}$$

$$E = \sum_{i=0}^{N-2} \left[ \frac{P_i + P_{i+1}}{2} \right] \cdot \frac{\Delta t_i}{3600} \quad \text{(kWh)}$$

Trapezoidal numerical integration accurately calculates energy across irregular intervals, missing sensor entries, and communication gaps without assuming fixed 5-minute intervals.

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

## Privacy, Security & Data Safety

- **100% Local-First**: Telemetry files and databases never leave your local machine.
- **Zero Cloud Databases**: No external cloud database required for core operations.
- **Safe Spreadsheet Processing**: Excel formula evaluation and macro execution are strictly disabled during ingestion.
- **Credential Protection**: Private energy records, database files (`*.db`), and local credentials are kept out of source control.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
