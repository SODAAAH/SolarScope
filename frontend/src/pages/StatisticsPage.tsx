import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption, PALETTE } from '../lib/theme';

export const StatisticsPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{ activeDatasetId: string }>();
  const [statsData, setStatsData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.getStatistics(activeDatasetId)
      .then(setStatsData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset first.</div>;
  }

  const baseOpt = getBaseEChartsOption();
  const durationOption = statsData?.profiles ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: 'axis' },
    legend: {
      data: ['Solar PV Duration Curve', 'Household Load Duration Curve'],
      textStyle: { fontSize: 11, color: '#64748B' },
      top: 0
    },
    xAxis: {
      ...baseOpt.xAxis,
      name: '% of Time Exceeded',
      data: statsData.profiles.pv.duration_curve.map((d: any) => `${d.time_percentage}%`)
    },
    yAxis: { ...baseOpt.yAxis, name: 'Power (kW)' },
    series: [
      {
        name: 'Solar PV Duration Curve',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: PALETTE.solar },
        data: statsData.profiles.pv.duration_curve.map((d: any) => d.power_kw)
      },
      {
        name: 'Household Load Duration Curve',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: PALETTE.load },
        data: statsData.profiles.load.duration_curve.map((d: any) => d.power_kw)
      }
    ]
  } : null;

  const corr = statsData?.correlations;
  const correlationOption = corr ? {
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const val = params.data[2];
        const c1 = corr.channels[params.data[0]];
        const c2 = corr.channels[params.data[1]];
        return `${c1} vs ${c2}: <b>${val}</b>`;
      }
    },
    grid: { height: '70%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: corr.channels,
      splitArea: { show: true },
      axisLabel: { interval: 0, rotate: 25, fontSize: 10 }
    },
    yAxis: {
      type: 'category',
      data: corr.channels,
      splitArea: { show: true },
      axisLabel: { fontSize: 10 }
    },
    visualMap: {
      min: -1,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#EA580C', '#F8FAFC', '#0D9488']
      }
    },
    series: [
      {
        name: 'Pearson Correlation',
        type: 'heatmap',
        data: corr.pearson_matrix.flatMap((row: number[], i: number) =>
          row.map((val: number, j: number) => [j, i, val])
        ),
        label: { show: true, fontSize: 11 },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' }
        }
      }
    ]
  } : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-lg font-semibold tracking-tight">Statistical Distributions & Correlation Analysis</h1>
        <p className="text-xs text-slate-500">Duration exceedance curves, Pearson correlation matrix, and parametric channel distributions.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <h2 className="text-xs font-semibold mb-3">Power Duration Exceedance Curves</h2>
          {durationOption && <EChartComponent option={durationOption} height={320} loading={loading} />}
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <h2 className="text-xs font-semibold mb-3">Pearson Correlation Matrix</h2>
          {correlationOption && <EChartComponent option={correlationOption} height={320} loading={loading} />}
        </div>
      </div>

      {statsData?.profiles && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-xs font-semibold">Parametric Descriptive Statistics</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Channel</th>
                  <th className="px-4 py-2.5 font-medium">Mean</th>
                  <th className="px-4 py-2.5 font-medium">Std Dev</th>
                  <th className="px-4 py-2.5 font-medium">Min</th>
                  <th className="px-4 py-2.5 font-medium">Median</th>
                  <th className="px-4 py-2.5 font-medium">Max</th>
                  <th className="px-4 py-2.5 font-medium">P10</th>
                  <th className="px-4 py-2.5 font-medium">P25</th>
                  <th className="px-4 py-2.5 font-medium">P75</th>
                  <th className="px-4 py-2.5 font-medium">P90</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px] tabular-nums">
                {Object.entries(statsData.profiles).map(([key, data]: [string, any]) => (
                  <tr key={key} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-2.5 font-sans font-semibold text-slate-800 dark:text-slate-200 uppercase">{key}</td>
                    <td className="px-4 py-2.5">{data.stats.mean}</td>
                    <td className="px-4 py-2.5">{data.stats.std}</td>
                    <td className="px-4 py-2.5">{data.stats.min}</td>
                    <td className="px-4 py-2.5 font-semibold text-slate-900 dark:text-slate-100">{data.stats.median}</td>
                    <td className="px-4 py-2.5">{data.stats.max}</td>
                    <td className="px-4 py-2.5">{data.stats.p10}</td>
                    <td className="px-4 py-2.5">{data.stats.p25}</td>
                    <td className="px-4 py-2.5">{data.stats.p75}</td>
                    <td className="px-4 py-2.5">{data.stats.p90}</td>
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
