import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption, PALETTE } from '../lib/theme';
import { format12HourTime, formatHourLabel12 } from '../lib/formatters';

export const ConsumptionPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{ activeDatasetId: string }>();
  const [consumption, setConsumption] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.getConsumption(activeDatasetId)
      .then(setConsumption)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset first.</div>;
  }

  const baseOpt = getBaseEChartsOption();
  const hourlyChartOption = consumption?.hourly_breakdown ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: 'axis' },
    xAxis: {
      ...baseOpt.xAxis,
      data: consumption.hourly_breakdown.map((h: any) => formatHourLabel12(h.hour))
    },
    yAxis: { ...baseOpt.yAxis, name: 'Demand (kWh)' },
    series: [
      {
        name: 'Household Consumption',
        type: 'bar',
        barWidth: '60%',
        itemStyle: { color: PALETTE.load, borderRadius: [3, 3, 0, 0] },
        data: consumption.hourly_breakdown.map((h: any) => h.energy_kwh)
      }
    ]
  } : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-lg font-semibold tracking-tight">Household Consumption Profile & Base-Load Audit</h1>
        <p className="text-xs text-slate-500">Analysis of continuous aggregate demand, base-load floors, peak-demand episodes, and diurnal consumption distributions.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Total Demand</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {consumption?.total_demand_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">24-hour integrated</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Base-Load Floor</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {consumption?.base_load_estimate_kw?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kW</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">5th percentile night floor</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Peak Demand Load</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {consumption?.peak_load_kw?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kW</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">At {consumption?.peak_load_time_12h || format12HourTime(consumption?.peak_load_time)}</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Peak-to-Average Ratio</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {consumption?.peak_to_average_ratio}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Load factor: {consumption?.load_factor}</span>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-3">Hourly Household Demand Breakdown (kWh)</h2>
        {hourlyChartOption && <EChartComponent option={hourlyChartOption} height={300} loading={loading} />}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <h2 className="text-xs font-semibold mb-3">Diurnal Demand Breakdown</h2>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">Daytime Consumption (6:00 AM - 6:00 PM)</span>
              <span className="font-mono font-medium">{consumption?.daytime_demand_kwh?.toFixed(2)} kWh</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">Nighttime Consumption (6:00 PM - 6:00 AM)</span>
              <span className="font-mono font-medium">{consumption?.nighttime_demand_kwh?.toFixed(2)} kWh</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-500">Demand Coinciding with Active Solar (PV &gt; 100 W)</span>
              <span className="font-mono font-medium">{consumption?.coincident_solar_load_kwh?.toFixed(2)} kWh</span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <h2 className="text-xs font-semibold mb-3">Flexible Load Shifting Potential</h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            Of the {consumption?.nighttime_demand_kwh?.toFixed(2)} kWh consumed at night, approximately {((consumption?.base_load_estimate_kw || 0.69) * 12).toFixed(1)} kWh represents non-shiftable baseline continuous equipment (refrigeration, standby loads, router). The remaining ~6-8 kWh represents intermittent loads (appliances, air conditioning, pumps) suitable for daytime solar optimization.
          </p>
        </div>
      </div>
    </div>
  );
};
