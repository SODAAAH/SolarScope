import React, { useEffect, useState } from "react";
import { Save, CheckCircle2, Sliders, Battery, Sun, Cpu, Loader2, RefreshCw, ShieldCheck, Server } from "lucide-react";
import { api, type SystemSettings, type AnalystDiagnosticEngineStats } from "../lib/api";

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings>({
    pv_capacity_kwp: 6.2,
    num_modules: 10,
    module_wattage: 620,
    panel_model: "Canadian Solar",
    panel_tech: "N-Type TOPCon bifacial",
    inverter_model: "SUN-6K-SG06LP1-EU-CM2",
    inverter_power_kw: 6.0,
    inverter_serial: "2604282202",
    inverter_max_apparent_va: 6600.0,
    inverter_max_battery_current_a: 135.0,
    mppt_voltage_min_v: 150.0,
    mppt_voltage_max_v: 425.0,
    pv_voltage_max_v: 500.0,
    mppt_max_current_a: 18.0,
    logger_serial: "1251892903",
    logger_firmware: "MW4_32_5407_SS_04_00.00.00.13",
    logger_interval_min: 5,
    battery_model: "MENRED ESS",
    battery_chemistry: "LFP",
    battery_voltage: 51.2,
    battery_ah: 314.0,
    battery_capacity_kwh: 16.08,
    usable_capacity_kwh: 12.86,
    reserve_soc: 20.0,
    bms_max_charge_a: 100.0,
    bms_max_discharge_a: 100.0,
    max_charge_kw: 5.12,
    max_discharge_kw: 5.12,
    battery_efficiency: 0.95,
    import_tariff: 11.50,
    export_tariff: 0.0,
    currency: "PHP",
    timezone: "Asia/Manila"
  });

  const [loading, setLoading] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const [mcpStats, setMcpStats] = useState<AnalystDiagnosticEngineStats | null>(null);
  const [mcpLoading, setMcpLoading] = useState(false);

  const fetchMcpStats = async () => {
    setMcpLoading(true);
    try {
      const data = await api.getAnalystPerformance();
      setMcpStats(data);
    } catch {
      setMcpStats(null);
    } finally {
      setMcpLoading(false);
    }
  };

  useEffect(() => {
    api.getSettings()
      .then(res => setSettings(prev => ({ ...prev, ...res })))
      .catch(err => console.error(err));
    fetchMcpStats();
  }, []);

  const handleChange = (key: keyof SystemSettings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSavedSuccess(false);
    try {
      await api.updateSettings(settings);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System Settings & Verified Hardware Profile
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
            Physical hardware nameplates, inverter electrical limits, battery BMS thresholds, and tariff defaults.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <Sun className="w-5 h-5 text-amber-500 shrink-0" />
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Photovoltaic Array Specifications
              </h2>
            </div>
            {savedSuccess && (
              <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1 rounded-full">
                <CheckCircle2 className="w-4 h-4" />
                Settings Saved
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Panel Manufacturer
              </label>
              <input
                type="text"
                value={settings.panel_model ?? ""}
                onChange={(e) => handleChange("panel_model", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Cell Technology
              </label>
              <input
                type="text"
                value={settings.panel_tech ?? ""}
                onChange={(e) => handleChange("panel_tech", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Module Count
              </label>
              <input
                type="number"
                value={settings.num_modules}
                onChange={(e) => handleChange("num_modules", parseInt(e.target.value, 10))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Total Installed PV (kWp)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.pv_capacity_kwp}
                onChange={(e) => handleChange("pv_capacity_kwp", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Cpu className="w-5 h-5 text-blue-500 shrink-0" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Hybrid Inverter & Cloud Logger Hardware
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Inverter Model
              </label>
              <input
                type="text"
                value={settings.inverter_model ?? ""}
                onChange={(e) => handleChange("inverter_model", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Inverter Serial
              </label>
              <input
                type="text"
                value={settings.inverter_serial ?? ""}
                onChange={(e) => handleChange("inverter_serial", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Rated AC Power (kW)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.inverter_power_kw}
                onChange={(e) => handleChange("inverter_power_kw", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Logger Serial
              </label>
              <input
                type="text"
                value={settings.logger_serial ?? ""}
                onChange={(e) => handleChange("logger_serial", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Battery className="w-5 h-5 text-teal-600 shrink-0" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Battery Storage & BMS Current Thresholds
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Battery Manufacturer / Model
              </label>
              <input
                type="text"
                value={settings.battery_model ?? ""}
                onChange={(e) => handleChange("battery_model", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Nominal Capacity (kWh)
              </label>
              <input
                type="number"
                step="0.01"
                value={settings.battery_capacity_kwh}
                onChange={(e) => handleChange("battery_capacity_kwh", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Reserve Safety SOC (%)
              </label>
              <input
                type="number"
                step="1"
                value={settings.reserve_soc}
                onChange={(e) => handleChange("reserve_soc", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                BMS Discharge Limit (A)
              </label>
              <input
                type="number"
                step="1"
                value={settings.bms_max_discharge_a ?? 100.0}
                onChange={(e) => handleChange("bms_max_discharge_a", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Sliders className="w-5 h-5 text-slate-600 shrink-0" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Utility & Regional Configuration
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Currency Code
              </label>
              <input
                type="text"
                value={settings.currency}
                onChange={(e) => handleChange("currency", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Timezone
              </label>
              <input
                type="text"
                value={settings.timezone}
                onChange={(e) => handleChange("timezone", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Baseline Tariff (PHP/kWh)
              </label>
              <input
                type="number"
                step="0.01"
                value={settings.import_tariff}
                onChange={(e) => handleChange("import_tariff", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Feed-in / Export Rate
              </label>
              <input
                type="number"
                step="0.01"
                value={settings.export_tariff}
                onChange={(e) => handleChange("export_tariff", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-4 sm:p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-amber-600 shrink-0" />
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  Deye Open MCP Integration & Diagnostic Engine
                </h3>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {mcpLoading ? (
                <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Checking MCP Status...
                </span>
              ) : mcpStats?.mcp_connected ? (
                <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  MCP Server Active
                </span>
              ) : (
                <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  MCP Configured
                </span>
              )}
              <button
                type="button"
                onClick={fetchMcpStats}
                disabled={mcpLoading}
                className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                title="Refresh MCP Diagnostics"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${mcpLoading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">Analysis Architecture</div>
              <div className="mt-1 font-semibold text-slate-800 dark:text-slate-200 text-sm">
                Dual-Path Deterministic
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                Fast Path (<strong className="text-emerald-600 dark:text-emerald-400">&lt;10ms</strong>) + MCP Diagnostics
              </div>
            </div>

            <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">Security Guard</div>
              <div className="mt-1 font-semibold text-emerald-600 dark:text-emerald-400 text-sm flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" />
                Read-Only Enforced
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                Write & control tools hard-blocked
              </div>
            </div>

            <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">Inference Overhead</div>
              <div className="mt-1 font-semibold text-slate-800 dark:text-slate-200 text-sm">
                Zero Local AI
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                No LLM or background models
              </div>
            </div>

            <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">Target Station</div>
              <div className="mt-1 font-semibold text-slate-800 dark:text-slate-200 text-sm font-mono">
                {mcpStats?.station_name || "Mam Micah"}
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                ID: {mcpStats?.station_id || "62805884"}
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                Official Deye Open MCP Endpoint
              </div>
              <span className="px-2.5 py-0.5 text-xs font-mono rounded bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 w-fit">
                Streamable HTTP Transport
              </span>
            </div>
            <div className="font-mono text-xs text-slate-600 dark:text-slate-400 bg-white dark:bg-slate-900 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 break-all">
              {mcpStats?.mcp_endpoint || "https://developer.deyecloud.com/openmcp/mcp"}
            </div>
            <div className="text-xs text-slate-500">
              Verified Read-Only Tool Allowlist: <strong className="text-slate-700 dark:text-slate-300">get_station_latest</strong>, <strong className="text-slate-700 dark:text-slate-300">station_history</strong>, <strong className="text-slate-700 dark:text-slate-300">station_history_power</strong>, <strong className="text-slate-700 dark:text-slate-300">get_device_latest</strong>, <strong className="text-slate-700 dark:text-slate-300">device_history</strong>, <strong className="text-slate-700 dark:text-slate-300">device_alert_list</strong>.
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="w-full sm:w-auto justify-center px-6 py-2.5 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-semibold rounded-lg transition-colors flex items-center gap-2 shadow-xs disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{loading ? "Saving..." : "Save System Settings"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
