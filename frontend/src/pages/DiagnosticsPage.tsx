import React, { useState, useEffect } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Scale, AlertTriangle, ShieldCheck, CheckCircle2, AlertCircle } from "lucide-react";
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

  useEffect(() => {
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
        emphasis: { focus: "adjacency" },
        nodeAlign: "justify",
        data: balance.sankey_data.nodes,
        links: balance.sankey_data.links,
        lineStyle: { color: "gradient", curveness: 0.5, opacity: 0.35 },
        label: { color: "#475569", fontSize: 11 }
      }
    ]
  } : {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
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

      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-medium w-fit">
        <button
          onClick={() => setTab("balance")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "balance"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          <span>Flow Balance</span>
        </button>

        <button
          onClick={() => setTab("anomalies")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "anomalies"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Telemetry Events</span>
        </button>

        <button
          onClick={() => setTab("hardware")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-1 interactive-card">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Node Balance Check</span>
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

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-4 interactive-card">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Solar Self-Sufficiency</span>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2 tabular-nums">
                {((balance?.self_sufficiency_ratio || 0) * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Percentage of home electricity supplied by solar and battery</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-4 interactive-card">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Solar Self-Consumption</span>
              <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2 tabular-nums">
                {((balance?.self_consumption_ratio || 0) * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Percentage of solar electricity used inside the home</p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm card-stagger-4 interactive-card">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Energy Flow Distribution (Sankey Flow)
            </h3>
            <EChartComponent option={sankeyOption} height="360px" />
          </div>
        </div>
      )}

      {currentTab === "anomalies" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Filter Severity:</span>
            <div className="flex gap-1.5">
              {["ALL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
                <button
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
                  <div className="flex-1">
                    <div className="flex justify-between items-center">
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
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Verified Physical Hardware Thresholds
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">Deye Hybrid Inverter</span>
                <div className="flex justify-between text-slate-500"><span>Model:</span><span className="font-mono text-slate-700 dark:text-slate-300">{settings?.inverter_model || "SUN-6K-SG06LP1-EU-CM2"}</span></div>
                <div className="flex justify-between text-slate-500"><span>Serial:</span><span className="font-mono text-slate-700 dark:text-slate-300">{settings?.inverter_serial || "2604282202"}</span></div>
                <div className="flex justify-between text-slate-500"><span>Rated Continuous:</span><span className="font-mono text-slate-700 dark:text-slate-300">{settings?.inverter_power_kw ? `${settings.inverter_power_kw * 1000} W` : "6,000 W"}</span></div>
                <div className="flex justify-between text-slate-500"><span>Max Apparent Output:</span><span className="font-mono text-slate-700 dark:text-slate-300">{settings?.inverter_max_apparent_va ? `${settings.inverter_max_apparent_va} VA` : "6,600 VA"}</span></div>
                <div className="flex justify-between text-slate-500"><span>Inverter Battery Max:</span><span className="font-mono text-slate-700 dark:text-slate-300">{settings?.inverter_max_battery_current_a ? `${settings.inverter_max_battery_current_a} A` : "135 A"}</span></div>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">MENRED ESS Battery</span>
                <div className="flex justify-between text-slate-500"><span>Chemistry:</span><span className="font-mono text-slate-700 dark:text-slate-300">LiFePO4</span></div>
                <div className="flex justify-between text-slate-500"><span>Nominal Voltage:</span><span className="font-mono text-slate-700 dark:text-slate-300">51.2 V (48V class)</span></div>
                <div className="flex justify-between text-slate-500"><span>Capacity:</span><span className="font-mono text-slate-700 dark:text-slate-300">314 Ah (16.08 kWh)</span></div>
                <div className="flex justify-between text-slate-500"><span>BMS Current Limit:</span><span className="font-mono text-slate-700 dark:text-slate-300">100 A Enforced</span></div>
                <div className="flex justify-between text-slate-500"><span>Usable Storage:</span><span className="font-mono text-slate-700 dark:text-slate-300">12.86 kWh (80% DoD)</span></div>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">Canadian Solar Panels</span>
                <div className="flex justify-between text-slate-500"><span>Quantity:</span><span className="font-mono text-slate-700 dark:text-slate-300">10 Panels</span></div>
                <div className="flex justify-between text-slate-500"><span>Rating per Panel:</span><span className="font-mono text-slate-700 dark:text-slate-300">620 W TOPCon</span></div>
                <div className="flex justify-between text-slate-500"><span>Total Array:</span><span className="font-mono text-slate-700 dark:text-slate-300">6,200 Wp (6.2 kWp)</span></div>
                <div className="flex justify-between text-slate-500"><span>MPPT Voltage Range:</span><span className="font-mono text-slate-700 dark:text-slate-300">150V - 425V DC</span></div>
                <div className="flex justify-between text-slate-500"><span>Max PV Voltage:</span><span className="font-mono text-slate-700 dark:text-slate-300">500V DC</span></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
