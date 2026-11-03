import React, { useState, useEffect } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Calendar, Scale, BarChart3, AlertCircle, RefreshCw } from "lucide-react";
import { api, type DailySummaryItem } from "../lib/api";
import { formatDateMMDDYYYY } from "../lib/formatters";
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
  const [dateBStart, setDateBStart] = useState("2026-11-03");
  const [dateBEnd, setDateBEnd] = useState("2026-11-03");
  const [compareResult, setCompareResult] = useState<any>(null);
  const [comparing, setComparing] = useState(false);

  const [statsData, setStatsData] = useState<any>(null);

  const setTab = (tab: "summaries" | "compare" | "statistics") => {
    setSearchParams({ tab });
  };

  const loadData = () => {
    Promise.all([
      api.getHistoricalDaily(activeDatasetId || undefined),
      api.getHistoricalHourlyProfile(activeDatasetId || undefined),
      api.compareHistoricalPeriods(dateAStart, dateAEnd, dateBStart, dateBEnd),
      api.getStatistics(activeDatasetId || "all")
    ])
      .then(([daily, hourly, comp, stats]) => {
        setDailyData(daily || []);
        setHourlyProfiles(hourly || []);
        setCompareResult(comp);
        setStatsData(stats);

        if (daily && daily.length >= 2) {
          const firstDate = daily[0].date;
          const latestDate = daily[daily.length - 1].date;
          if (!dateAStart || dateAStart < firstDate) {
            setDateAStart(firstDate);
            setDateAEnd(firstDate);
          }
          if (!dateBStart || dateBStart > latestDate) {
            setDateBStart(latestDate);
            setDateBEnd(latestDate);
          }
        }
      })
      .catch(console.error);
  };

  useEffect(() => {
    loadData();
  }, [activeDatasetId]);

  const runComparison = async (startA = dateAStart, endA = dateAEnd, startB = dateBStart, endB = dateBEnd) => {
    setComparing(true);
    try {
      const data = await api.compareHistoricalPeriods(startA, endA, startB, endB);
      setCompareResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setComparing(false);
    }
  };

  const baseOpt = getBaseEChartsOption();

  const hourlyChartOption = {
    ...baseOpt,
    tooltip: {
      trigger: "axis",
      textStyle: { fontSize: 11 }
    },
    legend: {
      data: ["Solar Generation", "Household Load", "Grid Import"],
      bottom: 0,
      textStyle: { color: "#64748B", fontSize: 11 }
    },
    grid: { left: "4%", right: "4%", top: "8%", bottom: "16%", containLabel: true },
    xAxis: {
      type: "category",
      data: hourlyProfiles.map((p) => p.hour_label_12h),
      axisLine: { lineStyle: { color: "#94A3B8" } }
    },
    yAxis: {
      type: "value",
      name: "kW",
      axisLine: { lineStyle: { color: "#94A3B8" } },
      splitLine: { lineStyle: { color: "#E2E8F0", type: "dashed" } }
    },
    series: [
      {
        name: "Solar Generation",
        type: "line",
        smooth: true,
        showSymbol: false,
        itemStyle: { color: theme.colors.solar },
        data: hourlyProfiles.map((p) => p.pv_mean_kw ?? p.avg_pv_kw ?? 0)
      },
      {
        name: "Household Load",
        type: "line",
        smooth: true,
        showSymbol: false,
        itemStyle: { color: theme.colors.coral },
        data: hourlyProfiles.map((p) => p.load_mean_kw ?? p.avg_load_kw ?? 0)
      },
      {
        name: "Grid Import",
        type: "line",
        smooth: true,
        showSymbol: false,
        itemStyle: { color: theme.colors.teal },
        data: hourlyProfiles.map((p) => p.grid_mean_kw ?? p.avg_grid_import_kw ?? 0)
      }
    ]
  };

  const durationOption = statsData?.profiles ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: "axis", textStyle: { fontSize: 11 } },
    legend: {
      data: ["Solar PV Duration", "Household Load Duration"],
      textStyle: { fontSize: 11, color: "#64748B" },
      top: 0
    },
    xAxis: {
      ...baseOpt.xAxis,
      name: "% Time Exceeded",
      data: statsData.profiles.pv?.duration_curve?.map((d: any) => `${d.time_percentage}%`) || []
    },
    yAxis: { ...baseOpt.yAxis, name: "Power (kW)" },
    series: [
      {
        name: "Solar PV Duration",
        type: "line",
        showSymbol: false,
        data: statsData.profiles.pv?.duration_curve?.map((d: any) => d.power_kw) || [],
        itemStyle: { color: PALETTE.solar },
        areaStyle: { color: "rgba(245, 158, 11, 0.15)" }
      },
      {
        name: "Household Load Duration",
        type: "line",
        showSymbol: false,
        data: statsData.profiles.load?.duration_curve?.map((d: any) => d.power_kw) || [],
        itemStyle: { color: PALETTE.load },
        areaStyle: { color: "rgba(225, 29, 72, 0.1)" }
      }
    ]
  } : {};

  const minDate = dailyData.length > 0 ? dailyData[0].date : "2026-10-21";
  const maxDate = dailyData.length > 0 ? dailyData[dailyData.length - 1].date : "2026-11-03";

  const periodADays = compareResult?.period_a?.days_count ?? 0;
  const periodBDays = compareResult?.period_b?.days_count ?? 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Historical Trends & Summaries
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Aggregated calendar summaries, period-over-period comparisons, and multi-day statistical distributions.
          </p>
        </div>

        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-medium w-fit">
          <button
            onClick={() => setTab("summaries")}
            className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
              currentTab === "summaries"
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>Daily Summaries</span>
          </button>

          <button
            onClick={() => setTab("compare")}
            className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
              currentTab === "compare"
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <Scale className="w-3.5 h-3.5" />
            <span>Period Comparison</span>
          </button>

          <button
            onClick={() => setTab("statistics")}
            className={`px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
              currentTab === "statistics"
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Distributions</span>
          </button>
        </div>
      </div>

      {currentTab === "summaries" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Typical 24-Hour Diurnal Power Profile (kW)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Mean kW distribution across all {dailyData.length} observation days
                </p>
              </div>
            </div>
            <EChartComponent option={hourlyChartOption} height="320px" />
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Daily Verified Energy Ledger
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Audited daily generation, consumption, grid import, and battery throughput
                </p>
              </div>
              <span className="text-xs font-mono font-medium text-slate-500 px-2.5 py-1 bg-slate-100 dark:bg-slate-800 rounded-md">
                {dailyData.length} observation days
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-800 font-mono text-[11px]">
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
                      <td className="px-4 py-2.5 font-sans font-medium text-slate-800 dark:text-slate-200">{formatDateMMDDYYYY(d.date)}</td>
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
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Period Selection & Comparison
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Compare energy production, consumption, and utility dependence across any two historical days or multi-day intervals.
                </p>
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Library Range: {formatDateMMDDYYYY(minDate)} to {formatDateMMDDYYYY(maxDate)}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Period A Date</label>
                <input
                  type="date"
                  min={minDate}
                  max={maxDate}
                  value={dateAStart}
                  onChange={(e) => {
                    setDateAStart(e.target.value);
                    setDateAEnd(e.target.value);
                  }}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Period B Date</label>
                <input
                  type="date"
                  min={minDate}
                  max={maxDate}
                  value={dateBStart}
                  onChange={(e) => {
                    setDateBStart(e.target.value);
                    setDateBEnd(e.target.value);
                  }}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                />
              </div>

              <div>
                <button
                  onClick={() => runComparison()}
                  disabled={comparing || !dateAStart || !dateBStart}
                  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-1.5 shadow-xs disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${comparing ? "animate-spin" : ""}`} />
                  <span>Compare Periods</span>
                </button>
              </div>
            </div>

            {(periodADays === 0 || periodBDays === 0) && (
              <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
                <span>
                  Please select observation dates within the verified library range ({formatDateMMDDYYYY(minDate)} to {formatDateMMDDYYYY(maxDate)}). Unrecorded dates return 0 kWh.
                </span>
              </div>
            )}
          </div>

          {compareResult && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Solar Generation
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    {compareResult.period_a?.days_count || 1}d vs {compareResult.period_b?.days_count || 1}d
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Period A ({formatDateMMDDYYYY(dateAStart)}):</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      {(compareResult.period_a?.total_pv_kwh ?? compareResult.period_a?.pv_kwh ?? 0).toFixed(2)} kWh
                    </span>
                  </div>

                  <div className="flex justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Period B ({formatDateMMDDYYYY(dateBStart)}):</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      {(compareResult.period_b?.total_pv_kwh ?? compareResult.period_b?.pv_kwh ?? 0).toFixed(2)} kWh
                    </span>
                  </div>

                  <div className="pt-2 flex justify-between text-xs font-semibold text-amber-600 dark:text-amber-400">
                    <span>Delta:</span>
                    <span className="font-mono">
                      {compareResult.delta?.mean_daily_pv_kwh !== undefined
                        ? `${compareResult.delta.mean_daily_pv_kwh > 0 ? "+" : ""}${compareResult.delta.mean_daily_pv_kwh.toFixed(2)} kWh (${compareResult.delta.pv_pct_change > 0 ? "+" : ""}${compareResult.delta.pv_pct_change}%)`
                        : "0.00 kWh"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Household Consumption
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    {compareResult.period_a?.days_count || 1}d vs {compareResult.period_b?.days_count || 1}d
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Period A ({formatDateMMDDYYYY(dateAStart)}):</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      {(compareResult.period_a?.total_load_kwh ?? compareResult.period_a?.load_kwh ?? 0).toFixed(2)} kWh
                    </span>
                  </div>

                  <div className="flex justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Period B ({formatDateMMDDYYYY(dateBStart)}):</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      {(compareResult.period_b?.total_load_kwh ?? compareResult.period_b?.load_kwh ?? 0).toFixed(2)} kWh
                    </span>
                  </div>

                  <div className="pt-2 flex justify-between text-xs font-semibold text-rose-600 dark:text-rose-400">
                    <span>Delta:</span>
                    <span className="font-mono">
                      {compareResult.delta?.mean_daily_load_kwh !== undefined
                        ? `${compareResult.delta.mean_daily_load_kwh > 0 ? "+" : ""}${compareResult.delta.mean_daily_load_kwh.toFixed(2)} kWh (${compareResult.delta.load_pct_change > 0 ? "+" : ""}${compareResult.delta.load_pct_change}%)`
                        : "0.00 kWh"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Grid Purchases (TEI)
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    {compareResult.period_a?.days_count || 1}d vs {compareResult.period_b?.days_count || 1}d
                  </span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Period A ({formatDateMMDDYYYY(dateAStart)}):</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      {(compareResult.period_a?.total_grid_import_kwh ?? compareResult.period_a?.grid_import_kwh ?? 0).toFixed(2)} kWh
                    </span>
                  </div>

                  <div className="flex justify-between text-xs py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Period B ({formatDateMMDDYYYY(dateBStart)}):</span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      {(compareResult.period_b?.total_grid_import_kwh ?? compareResult.period_b?.grid_import_kwh ?? 0).toFixed(2)} kWh
                    </span>
                  </div>

                  <div className="pt-2 flex justify-between text-xs font-semibold text-blue-600 dark:text-blue-400">
                    <span>Delta:</span>
                    <span className="font-mono">
                      {compareResult.delta?.mean_daily_grid_kwh !== undefined
                        ? `${compareResult.delta.mean_daily_grid_kwh > 0 ? "+" : ""}${compareResult.delta.mean_daily_grid_kwh.toFixed(2)} kWh (${compareResult.delta.grid_pct_change > 0 ? "+" : ""}${compareResult.delta.grid_pct_change}%)`
                        : "0.00 kWh"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {currentTab === "statistics" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
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
