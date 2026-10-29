import React, { useEffect, useState } from "react";
import { Save, CheckCircle2, Sliders, Battery, Sun, BookOpen } from "lucide-react";
import { api, type SystemSettings } from "../lib/api";

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings>({
    pv_capacity_kwp: 5.0,
    num_modules: 10,
    module_wattage: 500,
    inverter_power_kw: 5.0,
    battery_chemistry: "LFP",
    battery_voltage: 51.2,
    battery_capacity_kwh: 15.0,
    usable_capacity_kwh: 11.25,
    reserve_soc: 25.0,
    max_charge_kw: 3.0,
    max_discharge_kw: 3.0,
    battery_efficiency: 0.95,
    import_tariff: 11.50,
    export_tariff: 0.0,
    currency: "PHP",
    timezone: "Asia/Manila"
  });

  const [loading, setLoading] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    api.getSettings()
      .then(res => setSettings(res))
      .catch(err => console.error(err));
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
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System Settings & Mathematical Reference
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Physical hardware nameplates, inverter operating thresholds, and transparent analytical formulas.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <Sun className="w-5 h-5 text-amber-500" />
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Photovoltaic Array & Inverter Specifications
              </h2>
            </div>
            {savedSuccess && (
              <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1 rounded-full">
                <CheckCircle2 className="w-4 h-4" />
                Settings Saved
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                PV Capacity (kWp)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.pv_capacity_kwp}
                onChange={(e) => handleChange("pv_capacity_kwp", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Number of Modules
              </label>
              <input
                type="number"
                value={settings.num_modules}
                onChange={(e) => handleChange("num_modules", parseInt(e.target.value, 10))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Module Wattage (W)
              </label>
              <input
                type="number"
                value={settings.module_wattage}
                onChange={(e) => handleChange("module_wattage", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Inverter Rating (kW)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.inverter_power_kw}
                onChange={(e) => handleChange("inverter_power_kw", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Battery className="w-5 h-5 text-teal-600" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Battery Storage & Cutoff Parameters
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Nominal Capacity (kWh)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.battery_capacity_kwh}
                onChange={(e) => handleChange("battery_capacity_kwh", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Reserve Cutoff SOC (%)
              </label>
              <input
                type="number"
                step="1"
                value={settings.reserve_soc}
                onChange={(e) => handleChange("reserve_soc", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Max Discharge Power (kW)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.max_discharge_kw}
                onChange={(e) => handleChange("max_discharge_kw", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Max Charge Power (kW)
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.max_charge_kw}
                onChange={(e) => handleChange("max_charge_kw", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Sliders className="w-5 h-5 text-slate-600" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Regional & Financial Defaults
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Currency Code
              </label>
              <input
                type="text"
                value={settings.currency}
                onChange={(e) => handleChange("currency", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
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
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Grid Import Rate
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.import_tariff}
                onChange={(e) => handleChange("import_tariff", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Grid Export / Feed-in Rate
              </label>
              <input
                type="number"
                step="0.1"
                value={settings.export_tariff}
                onChange={(e) => handleChange("export_tariff", parseFloat(e.target.value))}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-medium text-sm rounded-lg transition-colors flex items-center gap-2 shadow-sm"
          >
            <Save className="w-4 h-4" />
            {loading ? "Saving Configuration..." : "Save Configuration"}
          </button>
        </div>
      </form>

      <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <BookOpen className="w-5 h-5 text-slate-700 dark:text-slate-300" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Mathematical Methodology & Analytical Reference
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
          <div className="space-y-3">
            <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm mb-1">
                Trapezoidal Numerical Integration
              </h3>
              <p>
                Calculates cumulative energy (kWh) over irregular observation intervals dt = t_next - t_curr:
              </p>
              <div className="bg-white dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 font-mono text-[11px] my-1 text-slate-900 dark:text-slate-100">
                E = ∑ [ (P_i + P_i+1) / 2 ] * (Δt_i / 3600)
              </div>
              <p>
                Handles sampling variance (5m, 10m, 15m) without assuming equidistant time steps.
              </p>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm mb-1">
                Instantaneous Energy Balance Reconciliation
              </h3>
              <p>
                Evaluates physical conservation of energy across the inverter bus:
              </p>
              <div className="bg-white dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 font-mono text-[11px] my-1 text-slate-900 dark:text-slate-100">
                R(t) = P_PV(t) + P_Batt(t) + P_Grid(t) - P_Load(t)
              </div>
              <p>
                Residual $R(t) &gt; 0$ represents continuous inverter tare consumption (~70W), conversion thermal dissipation, and sensor calibration margins.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm mb-1">
                Self-Consumption & Self-Sufficiency
              </h3>
              <p>
                Quantifies on-site solar utilization and degree of independence from utility infrastructure:
              </p>
              <div className="bg-white dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 font-mono text-[11px] my-1 text-slate-900 dark:text-slate-100">
                Self-Consumption = (E_PV - E_Export) / E_PV
                <br />
                Self-Sufficiency = (E_Load - E_Import) / E_Load
              </div>
              <p>
                In zero-export setups, self-consumption is 100%, and self-sufficiency reflects total non-grid autonomy.
              </p>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm mb-1">
                Base Load Floor Estimation
              </h3>
              <p>
                Estimates continuous non-deferrable background consumption (refrigerators, standby devices, network gear) using the 5th percentile of observed load:
              </p>
              <div className="bg-white dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 font-mono text-[11px] my-1 text-slate-900 dark:text-slate-100">
                Base Load = Percentile_5(P_Load)
              </div>
              <p>
                Immune to temporary zero readings and intermittent spikes.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
