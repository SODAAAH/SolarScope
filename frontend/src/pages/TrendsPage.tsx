import React, { useState, useEffect } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Calendar, Scale, BarChart3 } from "lucide-react";
import { api, type DailySummaryItem } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { getBaseEChartsOption, theme, PALETTE } from "../lib/theme";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const TrendsPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get("tab") as "summaries" | "compare" | "statistics") || "summaries";

  const [dailyData, setDailyData] = useState<DailySummaryItem[]>([]);
  const [hourlyProfiles, setHourlyProfiles] = useState<any[]>([]);

  const [dateAStart, setDateAStart] = useState("2026-10-21");
  const [dateAEnd, setDateAEnd] = useState("2026-10-21");
  const [dateBStart, setDateBStart] = useState("2026-10-22");
  const [dateBEnd, setDateBEnd] = useState("2026-10-22");
  const [compareResult, setCompareResult] = useState<any>(null);

  const [statsData, setStatsData] = useState<any>(null);

  const setTab = (tab: "summaries" | "compare" | "statistics") => {
    setSearchParams({ tab });
  };

  useEffect(() => {
    Promise.all([
      api.getHistoricalDaily(activeDatasetId || undefined),
      api.getHistoricalHourlyProfile(activeDatasetId || undefined),
      api.compareHistoricalPeriods(dateAStart, dateAEnd, dateBStart, dateBEnd, activeDatasetId || undefined),
      activeDatasetId ? api.getStatistics(activeDatasetId) : Promise.resolve(null)
    ])
      .then(([daily, hourly, comp, stats]) => {
        setDailyData(daily);
        setHourlyProfiles(hourly);
        setCompareResult(comp);
        setStatsData(stats);
      })
      .catch(console.error);
  }, [activeDatasetId]);

  const runComparison = async () => {
    try {
      const data = await api.compareHistoricalPeriods(dateAStart, dateAEnd, dateBStart, dateBEnd, activeDatasetId || undefined);
      setCompareResult(data);
    } catch (err) {
      console.error(err);
    }
  };

  const hourlyChartOption = {
    tooltip: { trigger: "axis" },
    legend: { data: ["Solar Generation", "Household Load", "Grid Import"], bottom: 0, textStyle: { color: "#64748b" } },
    grid: { left: "4%", right: "4%", top: "8%", bottom: "16%", containLabel: true },
    xAxis: {
      type: "category",
      data: hourlyProfiles.map(p => p.hour_label_12h),
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: {
      type: "value",
      name: "kW",
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      { name: "Solar Generation", type: "line", smooth: true, showSymbol: false, itemStyle: { color: theme.colors.solar }, data: hourlyProfiles.map(p => p.avg_pv_kw) },
      { name: "Household Load", type: "line", smooth: true, showSymbol: false, itemStyle: { color: theme.colors.coral }, data: hourlyProfiles.map(p => p.avg_load_kw) },
      { name: "Grid Import", type: "line", smooth: true, showSymbol: false, itemStyle: { color: theme.colors.teal }, data: hourlyProfiles.map(p => p.avg_grid_import_kw) }
    ]
  };

  const baseOpt = getBaseEChartsOption();
  const durationOption = statsData?.profiles ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: "axis" },
    legend: { data: ["Solar PV Duration", "Household Load Duration"], textStyle: { fontSize: 11, color: "#64748B" }, top: 0 },
    xAxis: { ...baseOpt.xAxis, name: "% Time Exceeded", data: statsData.profiles.pv.duration_curve.map((d: any) => `${d.time_percentage}%`) },
    yAxis: { ...baseOpt.yAxis, name: "Power (kW)" },
    series: [
      { name: "Solar PV Duration", type: "line", showSymbol: false, data: statsData.profiles.pv.duration_curve.map((d: any) => d.power_kw), itemStyle: { color: PALETTE.solar }, areaStyle: { color: "rgba(245, 158, 11, 0.15)" } },
      { name: "Household Load Duration", type: "line", showSymbol: false, data: statsData.profiles.load.duration_curve.map((d: any) => d.power_kw), itemStyle: { color: PALETTE.load }, areaStyle: { color: "rgba(225, 29, 72, 0.1)" } }
    ]
  } : {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Historical Trends & Summaries
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Aggregated calendar summaries, period-over-period comparisons, and multi-day statistical distributions.
          </p>
        </div>
      </div>

      <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-6">
        <button
          onClick={() => setTab("summaries")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            currentTab === "summaries"
              ? "border-amber-600 text-amber-600 dark:border-amber-500 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Daily Summaries</span>
        </button>

        <button
          onClick={() => setTab("compare")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            currentTab === "compare"
              ? "border-amber-600 text-amber-600 dark:border-amber-500 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          <Scale className="w-4 h-4" />
          <span>Period Comparison</span>
        </button>

        <button
          onClick={() => setTab("statistics")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            currentTab === "statistics"
              ? "border-amber-600 text-amber-600 dark:border-amber-500 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Statistical Distributions</span>
        </button>
      </div>

      {currentTab === "summaries" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Typical 24-Hour Diurnal Power Profile (kW)
            </h3>
            <EChartComponent option={hourlyChartOption} height="320px" />
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Daily Verified Energy Ledger
              </h3>
              <span className="text-xs text-slate-500">{dailyData.length} observation days</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3 text-right">Solar (kWh)</th>
                    <th className="px-4 py-3 text-right">Load (kWh)</th>
                    <th className="px-4 py-3 text-right">Grid Import (kWh)</th>
                    <th className="px-4 py-3 text-right">Battery Chg (kWh)</th>
                    <th className="px-4 py-3 text-right">Battery Disch (kWh)</th>
                    <th className="px-4 py-3 text-right">Self-Sufficiency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                  {dailyData.map((d) => (
                    <tr key={d.date} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                      <td className="px-4 py-2.5 font-sans font-medium text-slate-800 dark:text-slate-200">{d.date}</td>
                      <td className="px-4 py-2.5 text-right text-amber-600 dark:text-amber-400 font-bold">{d.pv_kwh.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-right text-rose-600 dark:text-rose-400">{d.load_kwh.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-right text-blue-600 dark:text-blue-400">{d.grid_import_kwh.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-right">{d.battery_charge_kwh.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-right">{d.battery_discharge_kwh.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-right font-semibold text-emerald-600 dark:text-emerald-400">
                        {((d.self_sufficiency_ratio || 0) * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {currentTab === "compare" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Period Selection & Comparison
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Period A Date</label>
                <input
                  type="date"
                  value={dateAStart}
                  onChange={(e) => { setDateAStart(e.target.value); setDateAEnd(e.target.value); }}
                  className="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Period B Date</label>
                <input
                  type="date"
                  value={dateBStart}
                  onChange={(e) => { setDateBStart(e.target.value); setDateBEnd(e.target.value); }}
                  className="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                />
              </div>
              <div>
                <button
                  onClick={runComparison}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  Compare Periods
                </button>
              </div>
            </div>
          </div>

          {compareResult && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Solar Generation Comparison</span>
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Period A:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{compareResult.period_a?.pv_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span>Period B:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{compareResult.period_b?.pv_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between text-xs font-semibold text-amber-600">
                    <span>Delta:</span>
                    <span>{compareResult.delta?.pv_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Consumption Comparison</span>
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Period A:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{compareResult.period_a?.load_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span>Period B:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{compareResult.period_b?.load_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between text-xs font-semibold text-rose-600">
                    <span>Delta:</span>
                    <span>{compareResult.delta?.load_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Grid Purchases Comparison</span>
                <div className="mt-2 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Period A:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{compareResult.period_a?.grid_import_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span>Period B:</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{compareResult.period_b?.grid_import_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-between text-xs font-semibold text-blue-600">
                    <span>Delta:</span>
                    <span>{compareResult.delta?.grid_import_kwh?.toFixed(2) || 0} kWh</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {currentTab === "statistics" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Power Duration Curves (% of Time Exceeded)
            </h3>
            <EChartComponent option={durationOption} height="360px" />
          </div>
        </div>
      )}
    </div>
  );
};
