import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption, PALETTE } from '../lib/theme';
import { format12HourTime } from '../lib/formatters';

export const BalancePage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{ activeDatasetId: string }>();
  const [balance, setBalance] = useState<any>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    Promise.all([
      api.getBalance(activeDatasetId),
      api.getTimeline(activeDatasetId)
    ])
      .then(([balRes, timeRes]) => {
        setBalance(balRes);
        setTimeline(timeRes);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset first.</div>;
  }

  const sankeyOption = balance?.sankey_data ? {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      textStyle: { fontSize: 11 }
    },
    series: [
      {
        type: 'sankey',
        layout: 'none',
        emphasis: { focus: 'adjacency' },
        nodeAlign: 'justify',
        data: balance.sankey_data.nodes,
        links: balance.sankey_data.links,
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.35 },
        label: { color: '#475569', fontSize: 11, fontFamily: 'Inter' }
      }
    ]
  } : null;

  const baseOpt = getBaseEChartsOption();
  const residualChartOption = timeline ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: 'axis' },
    xAxis: {
      ...baseOpt.xAxis,
      data: timeline.timestamps.map((t: string) => format12HourTime(t))
    },
    yAxis: { ...baseOpt.yAxis, name: 'Residual (kW)', min: 0 },
    series: [
      {
        name: 'Instantaneous Residual (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: PALETTE.residual },
        areaStyle: { color: 'rgba(99, 102, 241, 0.08)' },
        data: timeline.residual_power_kw
      }
    ]
  } : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-lg font-semibold tracking-tight">Energy-Balance Reconciliation & Topology Model</h1>
        <p className="text-xs text-slate-500">Reconciliation of measured energy sources and sinks across hybrid inverter boundaries, residual analysis, and loss modeling.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Total Measured Sources</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {balance?.total_sources_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">PV ({balance?.pv_kwh}k) + Grid ({balance?.grid_imported_kwh}k) + Disch ({balance?.battery_discharged_kwh}k)</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Total Measured Sinks</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {balance?.total_sinks_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Load ({balance?.household_demand_kwh}k) + Charge ({balance?.battery_charged_kwh}k)</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Reconciliation Residual</span>
          <span className="text-xl font-bold tabular-nums text-indigo-600 dark:text-indigo-400">
            {balance?.residual_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">{balance?.residual_percent}% of total sources</span>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-3">Power Flow Sankey Diagram (kWh)</h2>
        {sankeyOption && <EChartComponent option={sankeyOption} height={340} loading={loading} />}
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-3">Instantaneous Residual Power Profile R(t) in kW</h2>
        {residualChartOption && <EChartComponent option={residualChartOption} height={240} loading={loading} />}
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-3">Multi-Factor Residual Decomposition</h2>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {balance?.contributing_factors?.map((f: any, idx: number) => (
            <div key={idx} className="py-2.5 flex items-start justify-between gap-4">
              <div>
                <span className="text-xs font-medium text-slate-900 dark:text-slate-100 block">{f.factor}</span>
                <span className="text-[11px] text-slate-500 leading-relaxed block mt-0.5">{f.description}</span>
              </div>
              <div className="text-xs font-mono font-semibold text-slate-800 dark:text-slate-200 shrink-0 tabular-nums">
                ~{f.estimated_impact_kwh?.toFixed(2)} kWh
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
