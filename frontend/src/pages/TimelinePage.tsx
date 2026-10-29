import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption, PALETTE } from '../lib/theme';
import { format12HourTime } from '../lib/formatters';

export const TimelinePage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{ activeDatasetId: string }>();
  const [timeline, setTimeline] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.getTimeline(activeDatasetId)
      .then(setTimeline)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset first.</div>;
  }

  const baseOpt = getBaseEChartsOption();
  const mainChartOption = timeline ? {
    ...baseOpt,
    tooltip: {
      ...baseOpt.tooltip,
      trigger: 'axis'
    },
    legend: {
      data: ['PV Power (kW)', 'Load (kW)', 'Grid (kW)', 'Battery (kW)', 'Residual (kW)'],
      textStyle: { fontSize: 11, color: '#64748B' },
      top: 0
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 20, bottom: 0 }
    ],
    xAxis: {
      ...baseOpt.xAxis,
      data: timeline.timestamps.map((t: string) => format12HourTime(t))
    },
    yAxis: {
      ...baseOpt.yAxis,
      name: 'Power (kW)'
    },
    series: [
      {
        name: 'PV Power (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: PALETTE.solar },
        data: timeline.pv_power_kw
      },
      {
        name: 'Load (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: PALETTE.load },
        data: timeline.load_power_kw
      },
      {
        name: 'Grid (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: PALETTE.grid },
        data: timeline.grid_power_kw
      },
      {
        name: 'Battery (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: PALETTE.battery },
        data: timeline.battery_power_kw
      },
      {
        name: 'Residual (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, type: 'dashed', color: PALETTE.residual },
        data: timeline.residual_power_kw
      }
    ]
  } : null;

  const socChartOption = timeline ? {
    ...baseOpt,
    legend: {
      data: ['Battery State of Charge (%)'],
      textStyle: { fontSize: 11, color: '#64748B' },
      top: 0
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 16, bottom: 0 }
    ],
    xAxis: {
      ...baseOpt.xAxis,
      data: timeline.timestamps.map((t: string) => format12HourTime(t))
    },
    yAxis: {
      ...baseOpt.yAxis,
      name: 'SOC (%)',
      min: 0,
      max: 100
    },
    series: [
      {
        name: 'Battery State of Charge (%)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        areaStyle: { color: 'rgba(2, 132, 199, 0.1)' },
        lineStyle: { width: 2, color: PALETTE.soc },
        data: timeline.soc_percent
      }
    ]
  } : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-lg font-semibold tracking-tight">Synchronized Power & Battery Timeline</h1>
        <p className="text-xs text-slate-500">Interactive multi-axis time-series visualization. Use the zoom slider or mousewheel to inspect micro-episodes.</p>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-2">Continuous Multi-Channel Power Profiles (kW)</h2>
        {mainChartOption && <EChartComponent option={mainChartOption} height={360} loading={loading} />}
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-2">Battery State of Charge Trajectory (%)</h2>
        {socChartOption && <EChartComponent option={socChartOption} height={220} loading={loading} />}
      </div>
    </div>
  );
};
