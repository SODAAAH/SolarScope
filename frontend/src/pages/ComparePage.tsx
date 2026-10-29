import React, { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Scale, ArrowUpRight, ArrowDownRight, Sun, Home, Zap } from "lucide-react";
import { api } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { theme } from "../lib/theme";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const ComparePage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [dateAStart, setDateAStart] = useState("2026-10-21");
  const [dateAEnd, setDateAEnd] = useState("2026-10-21");
  const [dateBStart, setDateBStart] = useState("2026-10-22");
  const [dateBEnd, setDateBEnd] = useState("2026-10-22");
  const [compareResult, setCompareResult] = useState<any>(null);
  const [weekdayWeekendData, setWeekdayWeekendData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runComparison = async () => {
    setLoading(true);
    try {
      const data = await api.compareHistoricalPeriods(dateAStart, dateAEnd, dateBStart, dateBEnd, activeDatasetId || undefined);
      setCompareResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runComparison();
    api.getWeekdaysVsWeekends(activeDatasetId || undefined)
      .then(setWeekdayWeekendData)
      .catch(console.error);
  }, [activeDatasetId]);

  const pA = compareResult?.period_a;
  const pB = compareResult?.period_b;
  const delta = compareResult?.delta;

  const weekdayWeekendChartOption = weekdayWeekendData ? {
    tooltip: { trigger: "axis" },
    legend: { data: ["Weekday Load", "Weekend Load"], bottom: 0, textStyle: { color: "#64748b" } },
    grid: { left: "4%", right: "4%", top: "8%", bottom: "16%", containLabel: true },
    xAxis: {
      type: "category",
      data: weekdayWeekendData.hours_12h,
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: {
      type: "value",
      name: "Load Power (kW)",
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      {
        name: "Weekday Load",
        type: "line",
        smooth: true,
        data: weekdayWeekendData.weekday_hourly_load_kw,
        itemStyle: { color: theme.colors.slate },
        lineStyle: { width: 3, color: theme.colors.slate }
      },
      {
        name: "Weekend Load",
        type: "line",
        smooth: true,
        data: weekdayWeekendData.weekend_hourly_load_kw,
        itemStyle: { color: theme.colors.coral },
        lineStyle: { width: 2.5, type: "dashed", color: theme.colors.coral }
      }
    ]
  } : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Period Comparison Laboratory
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Fair comparative analysis across dates, weeks, weather episodes, and weekday versus weekend consumption.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
          Select Periods for Normalized Comparison
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Period A Start
            </label>
            <input
              type="date"
              value={dateAStart}
              onChange={(e) => setDateAStart(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Period A End
            </label>
            <input
              type="date"
              value={dateAEnd}
              onChange={(e) => setDateAEnd(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Period B Start
            </label>
            <input
              type="date"
              value={dateBStart}
              onChange={(e) => setDateBStart(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Period B End
            </label>
            <input
              type="date"
              value={dateBEnd}
              onChange={(e) => setDateBEnd(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <button
              onClick={runComparison}
              disabled={loading}
              className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Scale className="w-4 h-4" />
              {loading ? "Comparing..." : "Run Comparison"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Solar Generation</span>
            <Sun className="w-4 h-4 text-amber-500" />
          </div>
          <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <div>
              <span className="text-[11px] text-slate-500 block">Period A Daily Mean</span>
              <span className="text-lg font-bold tabular-nums text-slate-800 dark:text-slate-200">
                {pA?.mean_daily_pv_kwh ?? 0} kWh
              </span>
            </div>
            <div>
              <span className="text-[11px] text-slate-500 block">Period B Daily Mean</span>
              <span className="text-lg font-bold tabular-nums text-amber-600 dark:text-amber-400">
                {pB?.mean_daily_pv_kwh ?? 0} kWh
              </span>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-xs font-medium pt-2 border-t border-slate-100 dark:border-slate-800">
            {delta?.mean_daily_pv_kwh >= 0 ? (
              <span className="text-emerald-600 flex items-center">
                <ArrowUpRight className="w-4 h-4 mr-0.5" /> +{delta?.mean_daily_pv_kwh} kWh ({delta?.pv_pct_change}%)
              </span>
            ) : (
              <span className="text-rose-600 flex items-center">
                <ArrowDownRight className="w-4 h-4 mr-0.5" /> {delta?.mean_daily_pv_kwh} kWh ({delta?.pv_pct_change}%)
              </span>
            )}
            <span className="text-slate-400">delta vs Period A</span>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Household Load</span>
            <Home className="w-4 h-4 text-slate-500" />
          </div>
          <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <div>
              <span className="text-[11px] text-slate-500 block">Period A Daily Mean</span>
              <span className="text-lg font-bold tabular-nums text-slate-800 dark:text-slate-200">
                {pA?.mean_daily_load_kwh ?? 0} kWh
              </span>
            </div>
            <div>
              <span className="text-[11px] text-slate-500 block">Period B Daily Mean</span>
              <span className="text-lg font-bold tabular-nums text-slate-800 dark:text-slate-200">
                {pB?.mean_daily_load_kwh ?? 0} kWh
              </span>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-xs font-medium pt-2 border-t border-slate-100 dark:border-slate-800">
            {delta?.mean_daily_load_kwh >= 0 ? (
              <span className="text-orange-600 flex items-center">
                <ArrowUpRight className="w-4 h-4 mr-0.5" /> +{delta?.mean_daily_load_kwh} kWh ({delta?.load_pct_change}%)
              </span>
            ) : (
              <span className="text-emerald-600 flex items-center">
                <ArrowDownRight className="w-4 h-4 mr-0.5" /> {delta?.mean_daily_load_kwh} kWh ({delta?.load_pct_change}%)
              </span>
            )}
            <span className="text-slate-400">delta vs Period A</span>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Grid Dependence</span>
            <Zap className="w-4 h-4 text-orange-500" />
          </div>
          <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <div>
              <span className="text-[11px] text-slate-500 block">Period A Dependence</span>
              <span className="text-lg font-bold tabular-nums text-slate-800 dark:text-slate-200">
                {pA ? (pA.avg_grid_dependence * 100).toFixed(1) : 0}%
              </span>
            </div>
            <div>
              <span className="text-[11px] text-slate-500 block">Period B Dependence</span>
              <span className="text-lg font-bold tabular-nums text-orange-600 dark:text-orange-400">
                {pB ? (pB.avg_grid_dependence * 100).toFixed(1) : 0}%
              </span>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-xs font-medium pt-2 border-t border-slate-100 dark:border-slate-800">
            {delta?.grid_dependence_change <= 0 ? (
              <span className="text-emerald-600 flex items-center">
                <ArrowDownRight className="w-4 h-4 mr-0.5" /> {(delta?.grid_dependence_change * 100).toFixed(1)}%
              </span>
            ) : (
              <span className="text-rose-600 flex items-center">
                <ArrowUpRight className="w-4 h-4 mr-0.5" /> +{(delta?.grid_dependence_change * 100).toFixed(1)}%
              </span>
            )}
            <span className="text-slate-400">shift in grid reliance</span>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Weekday vs Weekend Demand Profile (12-Hour Clock)
            </h2>
            <p className="text-xs text-slate-500">
              Comparing average household electrical demand profiles between workdays and weekends
            </p>
          </div>
        </div>
        {weekdayWeekendChartOption && (
          <EChartComponent option={weekdayWeekendChartOption} height="320px" />
        )}
      </div>
    </div>
  );
};
