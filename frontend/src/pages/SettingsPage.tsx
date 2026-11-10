import React, { useEffect, useState } from "react";
import {
  Save,
  CheckCircle2,
  Sliders,
  Battery,
  Sun,
  Cpu,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Server,
  MapPin,
  AlertCircle
} from "lucide-react";
import { api, type SystemSettings, type AnalystDiagnosticEngineStats } from "../lib/api";

const EMPTY_SETTINGS: SystemSettings = {
  station_name: "",
  location_name: "",
  latitude: 0,
  longitude: 0,
  pv_capacity_kwp: 0,
  num_modules: 0,
  module_wattage: 0,
  panel_model: "",
  panel_tech: "",
  inverter_model: "",
  inverter_power_kw: 0,
  inverter_serial: "",
  inverter_max_apparent_va: 0,
  inverter_max_battery_current_a: 0,
  mppt_voltage_min_v: 0,
  mppt_voltage_max_v: 0,
  pv_voltage_max_v: 0,
  mppt_max_current_a: 0,
  logger_serial: "",
  logger_firmware: "",
  logger_interval_min: 5,
  battery_model: "",
  battery_chemistry: "LFP",
  battery_voltage: 0,
  battery_ah: 0,
  battery_capacity_kwh: 0,
  usable_capacity_kwh: 0,
  reserve_soc: 20,
  bms_max_charge_a: 0,
  bms_max_discharge_a: 0,
  max_charge_kw: 0,
  max_discharge_kw: 0,
  battery_efficiency: 0.95,
  import_tariff: 0,
  export_tariff: 0,
  currency: "PHP",
  timezone: "Asia/Manila"
};

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings>(EMPTY_SETTINGS);
  const [loading, setLoading] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

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
      .then((res) => setSettings((prev) => ({ ...prev, ...res })))
      .catch((err) => console.error(err));
    fetchMcpStats();
  }, []);

  const handleChange = (key: keyof SystemSettings, value: string | number) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleFloatChange = (key: keyof SystemSettings, raw: string) => {
    if (raw.trim() === "") {
      handleChange(key, 0);
      return;
    }
    const parsed = parseFloat(raw);
    handleChange(key, Number.isFinite(parsed) ? parsed : 0);
  };

  const handleIntChange = (key: keyof SystemSettings, raw: string) => {
    if (raw.trim() === "") {
      handleChange(key, 0);
      return;
    }
    const parsed = parseInt(raw, 10);
    handleChange(key, Number.isFinite(parsed) ? parsed : 0);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSavedSuccess(false);
    setSaveError(null);
    try {
      const res = await api.updateSettings(settings);
      if (res?.settings) {
        setSettings((prev) => ({ ...prev, ...res.settings }));
      }
      setSavedSuccess(true);
      await fetchMcpStats();
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      setSaveError(err?.message || "Failed to save system settings.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System Settings & Hardware Profile
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
            Configure site coordinates, solar array specifications, inverter limits, battery BMS thresholds, and utility tariffs.
          </p>
        </div>
      </div>

      {saveError && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 text-xs text-red-700 dark:text-red-300 flex items-center gap-2"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{saveError}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <div className="flex items-center gap-2">
              <MapPin className="w-5 h-5 text-amber-600 shrink-0" />
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Station & Site Location
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
              <label htmlFor="station_name" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Station Name
              </label>
              <input
                id="station_name"
                type="text"
                placeholder="e.g. Home Solar Array"
                value={settings.station_name ?? ""}
                onChange={(e) => handleChange("station_name", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="location_name" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Location / City Label
              </label>
              <input
                id="location_name"
                type="text"
                placeholder="City, Province"
                value={settings.location_name ?? ""}
                onChange={(e) => handleChange("location_name", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="latitude" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Latitude (Weather API)
              </label>
              <input
                id="latitude"
                type="number"
                step="0.0001"
                placeholder="e.g. 14.5995"
                value={settings.latitude ?? 0}
                onChange={(e) => handleFloatChange("latitude", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="longitude" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Longitude (Weather API)
              </label>
              <input
                id="longitude"
                type="number"
                step="0.0001"
                placeholder="e.g. 120.9842"
                value={settings.longitude ?? 0}
                onChange={(e) => handleFloatChange("longitude", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Sun className="w-5 h-5 text-amber-500 shrink-0" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Photovoltaic Array Specifications
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label htmlFor="panel_model" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Panel Manufacturer
              </label>
              <input
                id="panel_model"
                type="text"
                placeholder="e.g. Monocrystalline Tier-1"
                value={settings.panel_model ?? ""}
                onChange={(e) => handleChange("panel_model", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="panel_tech" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Cell Technology
              </label>
              <input
                id="panel_tech"
                type="text"
                placeholder="e.g. N-Type TOPCon / PERC"
                value={settings.panel_tech ?? ""}
                onChange={(e) => handleChange("panel_tech", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="num_modules" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Module Count
              </label>
              <input
                id="num_modules"
                type="number"
                value={settings.num_modules ?? 0}
                onChange={(e) => handleIntChange("num_modules", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="module_wattage" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Wattage per Module (W)
              </label>
              <input
                id="module_wattage"
                type="number"
                step="1"
                value={settings.module_wattage ?? 0}
                onChange={(e) => handleFloatChange("module_wattage", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="pv_capacity_kwp" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Total Installed PV (kWp)
              </label>
              <input
                id="pv_capacity_kwp"
                type="number"
                step="0.01"
                value={settings.pv_capacity_kwp ?? 0}
                onChange={(e) => handleFloatChange("pv_capacity_kwp", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="mppt_voltage_min_v" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                MPPT Min Voltage (V)
              </label>
              <input
                id="mppt_voltage_min_v"
                type="number"
                step="1"
                value={settings.mppt_voltage_min_v ?? 0}
                onChange={(e) => handleFloatChange("mppt_voltage_min_v", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="mppt_voltage_max_v" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                MPPT Max Voltage (V)
              </label>
              <input
                id="mppt_voltage_max_v"
                type="number"
                step="1"
                value={settings.mppt_voltage_max_v ?? 0}
                onChange={(e) => handleFloatChange("mppt_voltage_max_v", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="pv_voltage_max_v" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Max PV Open-Circuit Voltage (V)
              </label>
              <input
                id="pv_voltage_max_v"
                type="number"
                step="1"
                value={settings.pv_voltage_max_v ?? 0}
                onChange={(e) => handleFloatChange("pv_voltage_max_v", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-4">
            <Cpu className="w-5 h-5 text-sky-600 shrink-0" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Hybrid Inverter & Cloud Logger Hardware
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label htmlFor="inverter_model" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Inverter Model
              </label>
              <input
                id="inverter_model"
                type="text"
                placeholder="e.g. Hybrid Inverter Model"
                value={settings.inverter_model ?? ""}
                onChange={(e) => handleChange("inverter_model", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="inverter_serial" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Inverter Serial
              </label>
              <input
                id="inverter_serial"
                type="text"
                placeholder="Inverter SN"
                value={settings.inverter_serial ?? ""}
                onChange={(e) => handleChange("inverter_serial", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="inverter_power_kw" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Rated AC Power (kW)
              </label>
              <input
                id="inverter_power_kw"
                type="number"
                step="0.1"
                value={settings.inverter_power_kw ?? 0}
                onChange={(e) => handleFloatChange("inverter_power_kw", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="inverter_max_apparent_va" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Max Apparent Output (VA)
              </label>
              <input
                id="inverter_max_apparent_va"
                type="number"
                step="10"
                value={settings.inverter_max_apparent_va ?? 0}
                onChange={(e) => handleFloatChange("inverter_max_apparent_va", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="inverter_max_battery_current_a" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Inverter Max Battery Current (A)
              </label>
              <input
                id="inverter_max_battery_current_a"
                type="number"
                step="1"
                value={settings.inverter_max_battery_current_a ?? 0}
                onChange={(e) => handleFloatChange("inverter_max_battery_current_a", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="logger_serial" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Logger Serial
              </label>
              <input
                id="logger_serial"
                type="text"
                placeholder="Data Logger SN"
                value={settings.logger_serial ?? ""}
                onChange={(e) => handleChange("logger_serial", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="logger_firmware" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Logger Firmware Version
              </label>
              <input
                id="logger_firmware"
                type="text"
                placeholder="Firmware version"
                value={settings.logger_firmware ?? ""}
                onChange={(e) => handleChange("logger_firmware", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="logger_interval_min" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Reporting Interval (min)
              </label>
              <input
                id="logger_interval_min"
                type="number"
                min="1"
                step="1"
                value={settings.logger_interval_min ?? 5}
                onChange={(e) => handleIntChange("logger_interval_min", e.target.value)}
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
              <label htmlFor="battery_model" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Battery Manufacturer / Model
              </label>
              <input
                id="battery_model"
                type="text"
                placeholder="e.g. ESS Battery Bank"
                value={settings.battery_model ?? ""}
                onChange={(e) => handleChange("battery_model", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="battery_chemistry" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Chemistry
              </label>
              <input
                id="battery_chemistry"
                type="text"
                placeholder="LFP"
                value={settings.battery_chemistry ?? "LFP"}
                onChange={(e) => handleChange("battery_chemistry", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="battery_voltage" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Nominal Voltage (V)
              </label>
              <input
                id="battery_voltage"
                type="number"
                step="0.1"
                value={settings.battery_voltage ?? 0}
                onChange={(e) => handleFloatChange("battery_voltage", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="battery_ah" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Amp-Hour Rating (Ah)
              </label>
              <input
                id="battery_ah"
                type="number"
                step="1"
                value={settings.battery_ah ?? 0}
                onChange={(e) => handleFloatChange("battery_ah", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="battery_capacity_kwh" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Nominal Capacity (kWh)
              </label>
              <input
                id="battery_capacity_kwh"
                type="number"
                step="0.01"
                value={settings.battery_capacity_kwh ?? 0}
                onChange={(e) => handleFloatChange("battery_capacity_kwh", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="usable_capacity_kwh" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Usable Capacity (kWh)
              </label>
              <input
                id="usable_capacity_kwh"
                type="number"
                step="0.01"
                value={settings.usable_capacity_kwh ?? 0}
                onChange={(e) => handleFloatChange("usable_capacity_kwh", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="reserve_soc" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Reserve Safety SOC (%)
              </label>
              <input
                id="reserve_soc"
                type="number"
                step="1"
                value={settings.reserve_soc ?? 20}
                onChange={(e) => handleFloatChange("reserve_soc", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="bms_max_discharge_a" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                BMS Discharge Limit (A)
              </label>
              <input
                id="bms_max_discharge_a"
                type="number"
                step="1"
                value={settings.bms_max_discharge_a ?? 0}
                onChange={(e) => handleFloatChange("bms_max_discharge_a", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="bms_max_charge_a" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                BMS Charge Limit (A)
              </label>
              <input
                id="bms_max_charge_a"
                type="number"
                step="1"
                value={settings.bms_max_charge_a ?? 0}
                onChange={(e) => handleFloatChange("bms_max_charge_a", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="max_charge_kw" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Max Charge Power (kW)
              </label>
              <input
                id="max_charge_kw"
                type="number"
                step="0.01"
                value={settings.max_charge_kw ?? 0}
                onChange={(e) => handleFloatChange("max_charge_kw", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="max_discharge_kw" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Max Discharge Power (kW)
              </label>
              <input
                id="max_discharge_kw"
                type="number"
                step="0.01"
                value={settings.max_discharge_kw ?? 0}
                onChange={(e) => handleFloatChange("max_discharge_kw", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="battery_efficiency" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Round-Trip Efficiency (0–1)
              </label>
              <input
                id="battery_efficiency"
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={settings.battery_efficiency ?? 0.95}
                onChange={(e) => handleFloatChange("battery_efficiency", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
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
              <label htmlFor="currency" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Currency Code
              </label>
              <input
                id="currency"
                type="text"
                value={settings.currency}
                onChange={(e) => handleChange("currency", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="timezone" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Timezone
              </label>
              <input
                id="timezone"
                type="text"
                value={settings.timezone}
                onChange={(e) => handleChange("timezone", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
              />
            </div>

            <div>
              <label htmlFor="import_tariff" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Baseline Tariff ({settings.currency || "PHP"}/kWh)
              </label>
              <input
                id="import_tariff"
                type="number"
                step="0.01"
                value={settings.import_tariff ?? 0}
                onChange={(e) => handleFloatChange("import_tariff", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
              />
            </div>

            <div>
              <label htmlFor="export_tariff" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Feed-in / Export Rate
              </label>
              <input
                id="export_tariff"
                type="number"
                step="0.01"
                value={settings.export_tariff ?? 0}
                onChange={(e) => handleFloatChange("export_tariff", e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
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
                <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-slate-400" />
                  Unconfigured
                </span>
              )}
              <button
                type="button"
                onClick={fetchMcpStats}
                disabled={mcpLoading}
                className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                title="Refresh MCP Diagnostics"
                aria-label="Refresh MCP Diagnostics"
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
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">Compute Engine</div>
              <div className="mt-1 font-semibold text-slate-800 dark:text-slate-200 text-sm">
                Deterministic Physics
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                Equation-driven calculations
              </div>
            </div>

            <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">Target Station</div>
              <div className="mt-1 font-semibold text-slate-800 dark:text-slate-200 text-sm font-mono truncate">
                {mcpStats?.station_name || settings.station_name || "Not set"}
              </div>
              <div className="text-[11px] text-slate-500 mt-1 font-mono">
                ID: {mcpStats?.station_id || "--"}
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
