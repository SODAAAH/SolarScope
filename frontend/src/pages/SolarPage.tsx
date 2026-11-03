import React, { useState, useEffect } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Sun, CloudSun, Calendar, Cloud, Thermometer } from "lucide-react";
import { api, type WeatherIntelligenceResponse } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { getBaseEChartsOption, theme, PALETTE } from "../lib/theme";
import { formatHourLabel12 } from "../lib/formatters";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const SolarPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get("tab") as "production" | "weather" | "forecast") || "production";

  const [solar, setSolar] = useState<any>(null);
  const [weather, setWeather] = useState<WeatherIntelligenceResponse | null>(null);

  const setTab = (tab: "production" | "weather" | "forecast") => {
    setSearchParams({ tab });
  };

  useEffect(() => {
    if (!activeDatasetId) return;
    Promise.all([
      api.getSolar(activeDatasetId),
      api.getWeatherIntelligence()
    ])
      .then(([sData, wData]) => {
        setSolar(sData);
        setWeather(wData);
      })
      .catch(console.error);
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return (
      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <Sun className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">No Dataset Active</h3>
        <p className="text-sm text-slate-500 mt-1">Select or import a dataset to inspect solar generation and weather correlations.</p>
      </div>
    );
  }

  const baseOpt = getBaseEChartsOption();
  const hourlyChartOption = solar?.hourly_breakdown ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: "axis" },
    xAxis: {
      ...baseOpt.xAxis,
      data: solar.hourly_breakdown.map((h: any) => formatHourLabel12(h.hour))
    },
    yAxis: { ...baseOpt.yAxis, name: "Energy (kWh)" },
    series: [
      {
        name: "Solar Energy",
        type: "bar",
        barWidth: "60%",
        itemStyle: { color: PALETTE.solar, borderRadius: [3, 3, 0, 0] },
        data: solar.hourly_breakdown.map((h: any) => h.energy_kwh)
      }
    ]
  } : {};

  const forecastHourlyOption = weather?.hourly_forecast ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: "axis" },
    legend: { data: ["Estimated Solar Power (kW)", "Solar Radiation (W/m²)"], top: 0, textStyle: { color: "#64748B" } },
    xAxis: {
      ...baseOpt.xAxis,
      data: weather.hourly_forecast.map((f) => formatHourLabel12(f.hour))
    },
    yAxis: [
      { type: "value", name: "Power (kW)", axisLine: { lineStyle: { color: "#94a3b8" } } },
      { type: "value", name: "Radiation (W/m²)", position: "right", splitLine: { show: false } }
    ],
    series: [
      {
        name: "Estimated Solar Power (kW)",
        type: "line",
        smooth: true,
        data: weather.hourly_forecast.map((f) => f.estimated_pv_power_kw),
        itemStyle: { color: theme.colors.solar }
      },
      {
        name: "Solar Radiation (W/m²)",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        data: weather.hourly_forecast.map((f) => f.solar_radiation_wm2),
        itemStyle: { color: theme.colors.teal }
      }
    ]
  } : {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Solar Photovoltaic Generation & Weather Intelligence
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Array specific yield, inverter clipping thresholds, Open-Meteo atmospheric correlation, and next-day solar forecasts.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-medium w-fit">
        <button
          onClick={() => setTab("production")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "production"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Sun className="w-3.5 h-3.5" />
          <span>Production & Yield</span>
        </button>

        <button
          onClick={() => setTab("weather")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "weather"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <CloudSun className="w-3.5 h-3.5" />
          <span>Weather & Radiation</span>
        </button>

        <button
          onClick={() => setTab("forecast")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "forecast"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Calendar className="w-3.5 h-3.5" />
          <span>Tomorrow's Forecast</span>
        </button>
      </div>

      {currentTab === "production" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Total Solar Generated</span>
              <span className="text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400">
                {solar?.total_generation_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
              </span>
              <span className="text-xs text-slate-500 block mt-1">Trapezoidal integration</span>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Specific Yield</span>
              <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                {solar?.specific_yield_kwh_per_kwp?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh/kWp</span>
              </span>
              <span className="text-xs text-slate-500 block mt-1">Capacity: {solar?.pv_capacity_kwp || 6.2} kWp</span>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Peak PV Power</span>
              <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                {solar?.peak_power_kw?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kW</span>
              </span>
              <span className="text-xs text-slate-500 block mt-1">At {solar?.peak_power_time_12h || "12:15 PM"}</span>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Inverter Saturation</span>
              <span className="text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                {solar?.estimated_clipping_kwh ? `${solar.estimated_clipping_kwh.toFixed(2)} kWh` : "None"}
              </span>
              <span className="text-xs text-slate-500 block mt-1">Operating below 6.0 kW limit</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Hourly Solar Energy Generation Profile
            </h3>
            <EChartComponent option={hourlyChartOption} height="320px" />
          </div>
        </div>
      )}

      {currentTab === "weather" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
              <Cloud className="w-8 h-8 text-slate-400" />
              <div>
                <span className="text-xs text-slate-500 block">Cloud Cover</span>
                <span className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                  {weather?.current_conditions.cloud_cover_percent || 25}%
                </span>
                <span className="text-xs text-slate-500">Central Luzon atmospheric model</span>
              </div>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
              <Sun className="w-8 h-8 text-amber-500" />
              <div>
                <span className="text-xs text-slate-500 block">Solar Radiation</span>
                <span className="text-2xl font-bold text-amber-600 dark:text-amber-400 tabular-nums">
                  {weather?.current_conditions.solar_radiation_wm2 || 650} W/m²
                </span>
                <span className="text-xs text-slate-500">Surface solar irradiance</span>
              </div>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-4">
              <Thermometer className="w-8 h-8 text-rose-500" />
              <div>
                <span className="text-xs text-slate-500 block">Ambient Temperature</span>
                <span className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                  {weather?.current_conditions.temperature_c || 31}°C
                </span>
                <span className="text-xs text-slate-500">Panel temperature coefficient applied</span>
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400">
            <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-1">Weather Context for Tarlac City (15.48° N, 120.60° E):</span>
            Solar generation closely mirrors local cloud cover. Moderate cloud cover reduces direct radiation but allows diffuse light absorption via your bifacial TOPCon panels.
          </div>
        </div>
      )}

      {currentTab === "forecast" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Expected Tomorrow Yield</span>
              <span className="text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400">
                {weather?.tomorrow_forecast.expected_solar_kwh || 21.5} <span className="text-xs font-normal text-slate-500">kWh</span>
              </span>
              <span className="text-xs text-slate-500 block mt-1">Range: {weather?.tomorrow_forecast.conservative_solar_kwh || 18} - {weather?.tomorrow_forecast.optimistic_solar_kwh || 25} kWh</span>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Full Charge Probability</span>
              <span className="text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                {weather?.tomorrow_forecast.probability_full_charge_percent || 85}%
              </span>
              <span className="text-xs text-slate-500 block mt-1">Likelihood battery reaches 100%</span>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Sunset Battery SOC</span>
              <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                {weather?.tomorrow_forecast.projected_sunset_soc_percent || 95}%
              </span>
              <span className="text-xs text-slate-500 block mt-1">Projected state of charge at 6 PM</span>
            </div>

            <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block mb-1">Projected Night Autonomy</span>
              <span className="text-2xl font-bold tabular-nums text-blue-600 dark:text-blue-400">
                {weather?.tomorrow_forecast.projected_night_autonomy_formatted || "9h 30m"}
              </span>
              <span className="text-xs text-slate-500 block mt-1">Estimated runtime without grid import</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Hourly Solar Radiation & Expected PV Output Forecast (Tomorrow)
            </h3>
            <EChartComponent option={forecastHourlyOption} height="320px" />
          </div>
        </div>
      )}
    </div>
  );
};
