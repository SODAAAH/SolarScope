import React, { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api, type DailySummaryItem } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { theme } from "../lib/theme";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const DailySummariesPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [activeTab, setActiveTab] = useState<"daily" | "weekly" | "monthly">("daily");
  const [dailyData, setDailyData] = useState<DailySummaryItem[]>([]);
  const [weeklyData, setWeeklyData] = useState<any[]>([]);
  const [monthlyData, setMonthlyData] = useState<any[]>([]);
  const [hourlyProfiles, setHourlyProfiles] = useState<any[]>([]);
  const [averages, setAverages] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getHistoricalDaily(activeDatasetId || undefined),
      api.getHistoricalWeekly(activeDatasetId || undefined),
      api.getHistoricalMonthly(activeDatasetId || undefined),
      api.getHistoricalHourlyProfile(activeDatasetId || undefined),
      api.getHistoricalAverages(activeDatasetId || undefined)
    ])
      .then(([daily, weekly, monthly, hourly, avg]) => {
        setDailyData(daily);
        setWeeklyData(weekly);
        setMonthlyData(monthly);
        setHourlyProfiles(hourly);
        setAverages(avg);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

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
      name: "Average Power (kW)",
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      {
        name: "Solar Generation",
        type: "line",
        smooth: true,
        data: hourlyProfiles.map(p => p.pv_mean_kw),
        itemStyle: { color: theme.colors.solar },
        lineStyle: { width: 3, color: theme.colors.solar }
      },
      {
        name: "Household Load",
        type: "line",
        smooth: true,
        data: hourlyProfiles.map(p => p.load_mean_kw),
        itemStyle: { color: theme.colors.slate },
        lineStyle: { width: 2.5, color: theme.colors.slate }
      },
      {
        name: "Grid Import",
        type: "line",
        smooth: true,
        data: hourlyProfiles.map(p => p.grid_mean_kw),
        itemStyle: { color: theme.colors.coral },
        lineStyle: { width: 2, color: theme.colors.coral }
      }
    ]
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Multi-Day Historical Intelligence & Daily Summaries
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Traceable calendar day summaries, ISO-week rollups, monthly totals, and 12-hour clock hour intelligence.
          </p>
        </div>

        <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab("daily")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === "daily"
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`}
          >
            Daily Summaries
          </button>
          <button
            onClick={() => setActiveTab("weekly")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === "weekly"
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`}
          >
            Weekly Rollups
          </button>
          <button
            onClick={() => setActiveTab("monthly")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === "monthly"
                ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
            }`}
          >
            Monthly Rollups
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
          Statistically Rigorous Definitions of Averages
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-slate-500 block">Time-Weighted Solar Power</span>
            <div className="text-xl font-bold tabular-nums text-amber-600 dark:text-amber-400 mt-1">
              {averages?.time_weighted_avg_pv_power_kw ?? 0} kW
            </div>
            <span className="text-[10px] text-slate-400 mt-1 block">Integrated energy / elapsed time</span>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-slate-500 block">Arithmetic Mean of PV Samples</span>
            <div className="text-xl font-bold tabular-nums text-slate-800 dark:text-slate-200 mt-1">
              {averages?.arithmetic_mean_pv_power_kw ?? 0} kW
            </div>
            <span className="text-[10px] text-slate-400 mt-1 block">Sample mean (raw row observations)</span>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-slate-500 block">Mean Daily Generation</span>
            <div className="text-xl font-bold tabular-nums text-amber-600 dark:text-amber-400 mt-1">
              {averages?.mean_daily_pv_energy_kwh ?? 0} kWh/day
            </div>
            <span className="text-[10px] text-slate-400 mt-1 block">Arithmetic mean of qualifying days</span>
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg border border-slate-100 dark:border-slate-800">
            <span className="text-slate-500 block">Median Daily Generation</span>
            <div className="text-xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400 mt-1">
              {averages?.median_daily_pv_energy_kwh ?? 0} kWh/day
            </div>
            <span className="text-[10px] text-slate-400 mt-1 block">Median day (robust to weather extremes)</span>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Clock Hour-of-Day Profile (12-Hour Format)
            </h2>
            <p className="text-xs text-slate-500">
              Mean observed power across all qualifying days by 12-hour clock hour
            </p>
          </div>
        </div>
        <EChartComponent option={hourlyChartOption} height="320px" loading={loading} />
      </div>

      {activeTab === "daily" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Daily Operating Summaries ({dailyData.length} Days)
            </h2>
            <span className="text-xs text-slate-500">All peak timestamps formatted in 12-hour format</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Date</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Solar (kWh)</th>
                  <th className="px-4 py-3 font-semibold">Demand (kWh)</th>
                  <th className="px-4 py-3 font-semibold">Grid Import (kWh)</th>
                  <th className="px-4 py-3 font-semibold">Self-Sufficiency</th>
                  <th className="px-4 py-3 font-semibold">Peak PV (12h Time)</th>
                  <th className="px-4 py-3 font-semibold">Peak Load (12h Time)</th>
                  <th className="px-4 py-3 font-semibold">SOC Min - Max</th>
                  <th className="px-4 py-3 font-semibold">Import Hours</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {dailyData.map(d => (
                  <tr key={d.date} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                      {d.date}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        d.status === "COMPLETE"
                          ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300"
                          : d.status === "PARTIAL"
                          ? "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300"
                          : "bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300"
                      }`}>
                        {d.status} ({d.coverage_pct}%)
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums font-semibold text-amber-600 dark:text-amber-400">
                      {d.pv_kwh.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums font-medium text-slate-800 dark:text-slate-200">
                      {d.load_kwh.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-orange-600 dark:text-orange-400">
                      {d.grid_import_kwh.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-teal-600 dark:text-teal-400">
                      {(d.self_sufficiency_ratio * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                      {d.peak_pv_kw.toFixed(2)} kW @ {d.peak_pv_time_12h || "N/A"}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                      {d.peak_load_kw.toFixed(2)} kW @ {d.peak_load_time_12h || "N/A"}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-slate-600 dark:text-slate-400">
                      {d.min_soc}% - {d.max_soc}%
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {d.grid_import_hours} hrs
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "weekly" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              ISO-Week Rollup Summaries ({weeklyData.length} Weeks)
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">ISO Week</th>
                  <th className="px-4 py-3 font-semibold">Date Range</th>
                  <th className="px-4 py-3 font-semibold">Observed Days</th>
                  <th className="px-4 py-3 font-semibold">Total Solar (kWh)</th>
                  <th className="px-4 py-3 font-semibold">Mean Daily Solar</th>
                  <th className="px-4 py-3 font-semibold">Median Daily Solar</th>
                  <th className="px-4 py-3 font-semibold">Total Demand</th>
                  <th className="px-4 py-3 font-semibold">Total Grid Import</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {weeklyData.map(w => (
                  <tr key={w.week} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                      {w.week}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                      {w.start_date} to {w.end_date}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {w.days_observed} days ({w.complete_days} complete)
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums font-semibold text-amber-600 dark:text-amber-400">
                      {w.total_pv_kwh} kWh
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {w.mean_daily_pv_kwh} kWh/day
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {w.median_daily_pv_kwh} kWh/day
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {w.total_load_kwh} kWh
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-orange-600 dark:text-orange-400">
                      {w.total_grid_import_kwh} kWh
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "monthly" && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Calendar Month Summaries ({monthlyData.length} Months)
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Month</th>
                  <th className="px-4 py-3 font-semibold">Days Observed</th>
                  <th className="px-4 py-3 font-semibold">Total Solar (kWh)</th>
                  <th className="px-4 py-3 font-semibold">Daily Mean ± Std</th>
                  <th className="px-4 py-3 font-semibold">Total Demand</th>
                  <th className="px-4 py-3 font-semibold">Total Grid Import</th>
                  <th className="px-4 py-3 font-semibold">Best Day (Solar)</th>
                  <th className="px-4 py-3 font-semibold">Worst Day (Solar)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {monthlyData.map(m => (
                  <tr key={m.month} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                      {m.month}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {m.days_observed} days ({m.complete_days} complete)
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums font-semibold text-amber-600 dark:text-amber-400">
                      {m.total_pv_kwh} kWh
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {m.mean_daily_pv_kwh} ± {m.std_daily_pv_kwh} kWh
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums">
                      {m.total_load_kwh} kWh
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-orange-600 dark:text-orange-400">
                      {m.total_grid_import_kwh} kWh
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-emerald-600 dark:text-emerald-400">
                      {m.best_day_date} ({m.best_day_pv_kwh} kWh)
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-rose-600 dark:text-rose-400">
                      {m.worst_day_date} ({m.worst_day_pv_kwh} kWh)
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
