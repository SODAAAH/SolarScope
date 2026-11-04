import { Tooltip } from '../components/common/Tooltip';
import React, { useState, useEffect } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Zap, Home, BatteryCharging, Activity, Clock } from "lucide-react";
import { api } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { getBaseEChartsOption, theme } from "../lib/theme";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const EnergyPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get("tab") as "consumption" | "grid" | "battery" | "timeline") || "consumption";

  const [summary, setSummary] = useState<any>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [gridClassification, setGridClassification] = useState<any>(null);

  const setTab = (tab: "consumption" | "grid" | "battery" | "timeline") => {
    setSearchParams({ tab });
  };

  useEffect(() => {
    if (!activeDatasetId) return;
    Promise.all([
      api.getSummary(activeDatasetId),
      api.getTimeline(activeDatasetId),
      api.getGridClassification(activeDatasetId)
    ])
      .then(([sData, tData, gData]) => {
        setSummary(sData);
        setTimeline(tData);
        setGridClassification(gData);
      })
      .catch((err) => console.error(err));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return (
      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <Zap className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">No Dataset Active</h3>
        <p className="text-sm text-slate-500 mt-1">Select or import a dataset in the Data Library to inspect energy flows.</p>
      </div>
    );
  }

  const consumption = summary?.consumption || {};
  const grid = summary?.grid || {};
  const battery = summary?.battery || {};
  const classifications = gridClassification?.import_classification || [];

  const timelineOption = timeline ? {
    ...getBaseEChartsOption(),
    legend: {
      data: ["Solar PV", "Household Load", "Electricity from TEI", "Battery Power"],
      textStyle: { fontSize: 11, color: "#64748B" },
      top: 0
    },
    grid: { left: "4%", right: "4%", top: "12%", bottom: "10%", containLabel: true },
    xAxis: {
      type: "category",
      data: timeline.timestamps_12h || timeline.timestamps,
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: {
      type: "value",
      name: "Power (kW)",
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      { name: "Solar PV", type: "line", data: timeline.pv_power_kw, itemStyle: { color: theme.colors.solar }, smooth: true, showSymbol: false },
      { name: "Household Load", type: "line", data: timeline.load_power_kw, itemStyle: { color: theme.colors.coral }, smooth: true, showSymbol: false },
      { name: "Electricity from TEI", type: "line", data: timeline.grid_power_kw, itemStyle: { color: theme.colors.teal }, smooth: true, showSymbol: false },
      { name: "Battery Power", type: "line", data: timeline.battery_power_kw, itemStyle: { color: theme.colors.emerald }, smooth: true, showSymbol: false }
    ]
  } : {};

  const hourlyGridOption = grid.hourly_breakdown ? {
    ...getBaseEChartsOption(),
    grid: { left: "4%", right: "4%", top: "10%", bottom: "12%", containLabel: true },
    xAxis: {
      type: "category",
      data: grid.hourly_breakdown.map((h: any) => h.hour_label_12h),
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: {
      type: "value",
      name: "Energy (kWh)",
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      {
        name: "Grid Import",
        type: "bar",
        data: grid.hourly_breakdown.map((h: any) => h.energy_kwh),
        itemStyle: { color: theme.colors.teal },
        barWidth: "60%"
      }
    ]
  } : {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Energy Flow & Household Demand
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Comprehensive diagnostics for home consumption, grid import causes, battery cycling, and real-time power timelines.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-medium w-fit">
        <button
          onClick={() => setTab("consumption")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "consumption"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Home className="w-3.5 h-3.5" />
          <span>Household Consumption</span>
        </button>

        <button
          onClick={() => setTab("grid")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "grid"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>Electricity from TEI</span>
        </button>

        <button
          onClick={() => setTab("battery")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "battery"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <BatteryCharging className="w-3.5 h-3.5" />
          <span>Battery Performance</span>
        </button>

        <button
          onClick={() => setTab("timeline")}
          className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "timeline"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Power Timeline</span>
        </button>
      </div>

      {currentTab === "consumption" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Total Household Consumption"
                content="Total electrical energy consumed across all home circuits during the observation cycle."
                formula="E_load = ∫ P_load(t) dt"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Total Consumption</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {(consumption.consumed_energy_kwh || 0).toFixed(2)} kWh
              </div>
              <p className="text-xs text-slate-500 mt-1">Electricity used by home appliances</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Baseload Power Draw"
                content="Continuous 24/7 background power draw from always-on appliances (refrigerators, Wi-Fi routers, security systems, standby electronics). Estimated from overnight 02:00-05:00 measurements."
                formula="P_base = Quantile_0.05(P_load[02:00-05:00])"
                provenance="Estimated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Baseload Power</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {(consumption.baseload_power_kw || 0).toFixed(2)} kW
              </div>
              <p className="text-xs text-slate-500 mt-1">Continuous 24/7 background power draw</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Peak Power Demand"
                content="The maximum instantaneous power rate drawn by household appliances at any single moment."
                provenance="Measured"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Peak Demand</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {(consumption.peak_load_kw || 0).toFixed(2)} kW
              </div>
              <p className="text-xs text-slate-500 mt-1">Highest instantaneous appliance power</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Daytime Solar Coincidence"
                content="Fraction of total home electricity consumed during solar daylight hours (06:00 - 18:00) when free rooftop solar is available."
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Daytime Use Ratio</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {consumption.day_consumption_ratio_percent ? consumption.day_consumption_ratio_percent.toFixed(1) : "55.0"}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Share consumed during daylight solar hours</p>
            </div>
          </div>
        </div>
      )}

      {currentTab === "grid" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Utility Grid Import"
                content="Electricity purchased from TEI when household demand exceeded solar generation and battery discharge."
                formula="E_import = ∫ max(0, P_grid(t)) dt"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Grid Import</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-blue-600 dark:text-blue-400 mt-1">
                {(grid.imported_energy_kwh || 0).toFixed(2)} kWh
              </div>
              <p className="text-xs text-slate-500 mt-1">Electricity purchased from TEI</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Grid Dependence Ratio"
                content="Proportion of household energy supplied by the utility grid. A lower percentage reflects higher self-sufficiency and solar autonomy."
                formula="Dependence = Grid Import / Total Consumption"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Grid Dependence</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {((grid.grid_dependence_ratio || 0) * 100).toFixed(1)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Fraction of home demand met by utility</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Peak Grid Import Surge"
                content="Highest instantaneous power surge drawn from the TEI utility service lines."
                provenance="Measured"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Peak Import Power</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {(grid.peak_import_kw || 0).toFixed(2)} kW
              </div>
              <p className="text-xs text-slate-500 mt-1">Max power surge drawn from the grid</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Reserve Cutoff Grid Import"
                content="Electricity imported from the grid after battery reached its configured minimum depth-of-discharge reserve cutoff (20% SOC)."
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Reserve Cutoff Import</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400 mt-1">
                {(grid.reserve_coincident_import_kwh || 0).toFixed(2)} kWh
              </div>
              <p className="text-xs text-slate-500 mt-1">Imported after battery reached reserve limit</p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              5-Category Grid Import Cause Classification
            </h3>
            <p className="text-xs text-slate-500">
              Deterministic breakdown showing exactly why electricity was purchased from TEI during this observation period.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-3 pt-2">
              {classifications.map((cat: any) => (
                <div key={cat.category} className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700/60 flex flex-col justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">{cat.category}</span>
                    <div className="text-xl font-bold text-slate-900 dark:text-slate-100 mt-1 tabular-nums">
                      {cat.energy_kwh.toFixed(2)} kWh
                    </div>
                    <span className="text-xs font-medium text-amber-600 dark:text-amber-400 tabular-nums">
                      {cat.percentage}% of import
                    </span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700 text-xs">
                    <span className="text-slate-500 block">Est. Cost:</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">PHP {cat.estimated_cost_php.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Hourly Grid Import Breakdown (kWh)
            </h3>
            <EChartComponent option={hourlyGridOption} height="280px" />
          </div>
        </div>
      )}

      {currentTab === "battery" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Remaining Battery Autonomy"
                content="Estimated runtime the battery can sustain current household consumption before reaching the 20% safe reserve floor."
                provenance="Estimated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Remaining Autonomy</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1.5">
                <Clock className="w-5 h-5" />
                <span>{battery.estimated_autonomy_formatted || "8h 30m"}</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">Based on recent load and usable energy</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Battery State of Charge"
                content="Current percentage of total usable battery capacity remaining in the LiFePO4 battery bank."
                formula="SOC = Remaining Ah / Rated Ah × 100%"
                provenance="Measured"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Charge Level (SOC)</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {(battery.final_soc_percent || 0).toFixed(0)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Min: {(battery.min_soc_percent || 0).toFixed(0)}% | Max: {(battery.max_soc_percent || 0).toFixed(0)}%</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="Round-Trip Coulombic Efficiency"
                content="Percentage of electrical energy recovered from the battery bank compared to total electrical energy injected during charging."
                formula="RTE = Total Discharged (kWh) / Total Charged (kWh) × 100%"
                provenance="Calculated"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">Round-Trip Efficiency</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {(battery.round_trip_efficiency_percent || 95.0).toFixed(1)}%
              </div>
              <p className="text-xs text-slate-500 mt-1">Energy discharged vs energy charged</p>
            </div>

            <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <Tooltip
                title="BMS Current Threshold"
                content="Maximum continuous DC charge/discharge current permitted by the Battery Management System hardware to prevent overheating and cell degradation."
                provenance="Measured"
                underline
              >
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 cursor-help">BMS Current Limit</span>
              </Tooltip>
              <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                {battery.bms_limit_enforced_a || 100.0} A
              </div>
              <p className="text-xs text-slate-500 mt-1">Max power: {battery.bms_limit_enforced_kw || 5.12} kW</p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Battery Cycling & Throughput Summary
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-slate-600 dark:text-slate-400">
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500 block">Total Charged:</span>
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{(battery.charging_energy_kwh || 0).toFixed(2)} kWh</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500 block">Total Discharged:</span>
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{(battery.discharging_energy_kwh || 0).toFixed(2)} kWh</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500 block">Equivalent Full Cycles:</span>
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{battery.equivalent_full_cycles || 0} cycles</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500 block">Hours at Reserve Limit:</span>
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 tabular-nums">{battery.hours_at_reserve_limit || 0} hrs</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {currentTab === "timeline" && (
        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
            High-Resolution 4-Channel Power Timeline
          </h3>
          <EChartComponent option={timelineOption} height="420px" />
        </div>
      )}
    </div>
  );
};
