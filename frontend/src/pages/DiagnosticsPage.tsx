import { Tooltip } from '../components/common/Tooltip';
import React, { useState, useEffect } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";
import { Scale, AlertTriangle, ShieldCheck, CheckCircle2, AlertCircle, Settings } from "lucide-react";
import { api } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { format12HourDateTime } from "../lib/formatters";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const DiagnosticsPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get("tab") as "balance" | "anomalies" | "hardware") || "balance";

  const [balance, setBalance] = useState<any>(null);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  const setTab = (tab: "balance" | "anomalies" | "hardware") => {
    setSearchParams({ tab });
  };

  const loadDiagnostics = () => {
    if (!activeDatasetId) return;
    setLoading(true);
    Promise.all([
      api.getBalance(activeDatasetId),
      api.getAnomalies(activeDatasetId),
      api.getSettings()
    ])
      .then(([bData, aData, sData]) => {
        setBalance(bData);
        setAnomalies(aData || []);
        setSettings(sData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!activeDatasetId) {
      api.getSettings().then(setSettings).catch(console.error);
      return;
    }
    loadDiagnostics();
    const handleRefresh = () => loadDiagnostics();
    const handleSettingsUpdated = () => {
      api.getSettings().then(setSettings).catch(console.error);
    };
    window.addEventListener("solarscope:sources-updated", handleRefresh);
    window.addEventListener("solarscope:settings-updated", handleSettingsUpdated);
    return () => {
      window.removeEventListener("solarscope:sources-updated", handleRefresh);
      window.removeEventListener("solarscope:settings-updated", handleSettingsUpdated);
    };
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return (
      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <Scale className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">No Dataset Active</h3>
        <p className="text-sm text-slate-500 mt-1">Select a dataset to view physics balance and anomaly diagnostics.</p>
      </div>
    );
  }

  const filteredAnomalies = anomalies.filter(a => filterSeverity === "ALL" || a.severity === filterSeverity);

  const sankeyOption = balance?.sankey_data ? {
    tooltip: { trigger: "item", triggerOn: "mousemove", textStyle: { fontSize: 11 } },
    series: [
      {
        type: "sankey",
        layout: "none",
        left: "2%",
        right: "16%",
        nodeWidth: 16,
        emphasis: { focus: "adjacency" },
        nodeAlign: "justify",
        data: balance.sankey_data.nodes,
        links: balance.sankey_data.links,
        lineStyle: { color: "gradient", curveness: 0.5, opacity: 0.35 },
        label: { color: "#475569", fontSize: 10 }
      }
    ]
  } : {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System Diagnostics & Physical Health
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            First-principles Kirchhoff energy accounting, statistical anomaly detection, and inverter/BMS electrical thresholds.
          </p>
        </div>
        {loading && (
          <div className="text-xs text-amber-600 dark:text-amber-400 font-medium">
            Updating diagnostics...
          </div>
        )}
      </div>

      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-medium w-full sm:w-fit max-w-full overflow-x-auto no-scrollbar">
        <button
          type="button"
          onClick={() => setTab("balance")}
          className={`shrink-0 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "balance"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          <span>Flow Balance</span>
        </button>

        <button
          type="button"
          onClick={() => setTab("anomalies")}
          className={`shrink-0 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "anomalies"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Telemetry Events</span>
        </button>

        <button
          type="button"
          onClick={() => setTab("hardware")}
          className={`shrink-0 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "hardware"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Hardware Limits</span>
        </button>
      </div>

      {currentTab === "balance" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
            <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-1 interactive-card">
              <Tooltip
                title="Kirchhoff Node Balance Check"
                content="First-principles verification that total energy into the inverter equals total energy out plus conversion and standby losses."
                formula="Residual = (PV + Import + Discharge) - (Load + Charge + Export)"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Node Balance Check</span>
              </Tooltip>
              <div className="flex items-center gap-2 mt-2">
                {balance?.is_balanced ? (
                  <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                ) : (
                  <AlertCircle className="w-6 h-6 text-amber-500" />
                )}
                <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  {balance?.is_balanced ? "Verified Kirchhoff Balance" : "Residual Imbalance Detected"}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Kirchhoff node residual: <span className="font-mono font-semibold">{balance?.residual_kwh || 0} kWh</span> ({balance?.residual_percent || 0}%)
              </p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-4 interactive-card">
              <Tooltip
                title="Solar Self-Sufficiency"
                content="The percentage of your home electricity supplied by your own solar panels and battery storage without relying on utility purchases."
                formula="Autonomy = 1 - (Grid Import / Total Load)"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Solar Self-Sufficiency</span>
              </Tooltip>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2 tabular-nums">
                {((balance?.self_sufficiency_ratio || 0) * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Percentage of home electricity supplied by solar and battery</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-4 interactive-card">
              <Tooltip
                title="Solar Self-Consumption"
                content="The percentage of generated solar electricity that was directly used by your home appliances or stored in your battery rather than exported."
                formula="Self-Consumption = (Total PV - Export) / Total PV"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Solar Self-Consumption</span>
              </Tooltip>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2 tabular-nums">
                {((balance?.self_consumption_ratio || 0) * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Percentage of solar electricity used inside the home</p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-4 interactive-card">
            <Tooltip
              title="Energy Flow Distribution"
              content="Sankey diagram showing conservation of energy: tracing energy origins (solar PV, utility grid, battery discharge) to destinations (home consumption, battery storage, and inverter standby tare)."
              position="bottom"
            >
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4 cursor-help">
                Energy Flow Distribution (Sankey Flow)
              </h3>
            </Tooltip>
            <EChartComponent option={sankeyOption} height="340px" />
          </div>
        </div>
      )}

      {currentTab === "anomalies" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-slate-500">Filter Severity:</span>
            <div className="flex flex-wrap gap-1.5">
              {["ALL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
                <button
                  type="button"
                  key={sev}
                  onClick={() => setFilterSeverity(sev)}
                  className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                    filterSeverity === sev
                      ? "bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200"
                  }`}
                >
                  {sev}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            {filteredAnomalies.length === 0 ? (
              <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-500 text-xs">
                No anomalies detected for the selected filter.
              </div>
            ) : (
              filteredAnomalies.map((item, idx) => (
                <div key={idx} className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-start gap-3">
                  <AlertTriangle className={`w-5 h-5 shrink-0 mt-0.5 ${item.severity === "HIGH" ? "text-rose-500" : item.severity === "MEDIUM" ? "text-amber-500" : "text-blue-500"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title || item.type}</span>
                      <span className="text-xs text-slate-500 font-mono">{format12HourDateTime(item.timestamp)}</span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">{item.description}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {currentTab === "hardware" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <Tooltip
                title="Hardware Specification Limits"
                content="Physical nameplate ratings, continuous inverter thresholds, and BMS firmware cutoff parameters governing safe system dispatch."
                position="bottom"
              >
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 cursor-help">
                  Verified Physical Hardware Thresholds
                </h3>
              </Tooltip>
              <Link
                to="/settings"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-600 dark:text-amber-400 hover:underline w-fit"
              >
                <Settings className="w-3.5 h-3.5" />
                <span>Configure in System Settings</span>
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  {settings?.inverter_model || "Hybrid Inverter"}
                </span>
                <div className="flex justify-between gap-2 text-slate-500"><span>Model:</span><span className="font-mono text-slate-700 dark:text-slate-300 break-all text-right">{settings?.inverter_model || "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Serial:</span><span className="font-mono text-slate-700 dark:text-slate-300 break-all text-right">{settings?.inverter_serial || "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Rated Continuous:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.inverter_power_kw ? `${Math.round(settings.inverter_power_kw * 1000).toLocaleString()} W` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Max Apparent Output:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.inverter_max_apparent_va ? `${Number(settings.inverter_max_apparent_va).toLocaleString()} VA` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Inverter Battery Max:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.inverter_max_battery_current_a ? `${settings.inverter_max_battery_current_a} A` : "Not set"}</span></div>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  {settings?.battery_model || "Battery Storage System"}
                </span>
                <div className="flex justify-between gap-2 text-slate-500"><span>Chemistry:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.battery_chemistry || "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Nominal Voltage:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.battery_voltage ? `${settings.battery_voltage} V` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Capacity:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{(settings?.battery_ah || settings?.battery_capacity_kwh) ? `${settings?.battery_ah ? `${settings.battery_ah} Ah ` : ""}${settings?.battery_capacity_kwh ? `(${settings.battery_capacity_kwh} kWh)` : ""}`.trim() : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>BMS Current Limit:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{(settings?.bms_max_charge_a || settings?.bms_max_discharge_a) ? `${settings?.bms_max_charge_a || 0} A Chg / ${settings?.bms_max_discharge_a || 0} A Disch` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Usable Storage:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.usable_capacity_kwh ? `${settings.usable_capacity_kwh} kWh` : "Not set"}</span></div>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  {settings?.panel_model || "Solar PV Array"}
                </span>
                <div className="flex justify-between gap-2 text-slate-500"><span>Quantity:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.num_modules ? `${settings.num_modules} Panels` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Rating per Panel:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{(settings?.module_wattage || settings?.panel_tech) ? `${settings?.module_wattage ? `${settings.module_wattage} W ` : ""}${settings?.panel_tech || ""}`.trim() : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Total Array:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.pv_capacity_kwp ? `${Math.round(settings.pv_capacity_kwp * 1000).toLocaleString()} Wp (${settings.pv_capacity_kwp} kWp)` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>MPPT Voltage Range:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{(settings?.mppt_voltage_min_v || settings?.mppt_voltage_max_v) ? `${settings?.mppt_voltage_min_v || 0}V - ${settings?.mppt_voltage_max_v || 0}V DC` : "Not set"}</span></div>
                <div className="flex justify-between gap-2 text-slate-500"><span>Max PV Voltage:</span><span className="font-mono text-slate-700 dark:text-slate-300 text-right">{settings?.pv_voltage_max_v ? `${settings.pv_voltage_max_v}V DC` : "Not set"}</span></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
