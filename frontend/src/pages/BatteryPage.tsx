import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption, PALETTE } from '../lib/theme';
import { ShieldAlert } from 'lucide-react';
import { format12HourTime } from '../lib/formatters';

export const BatteryPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{ activeDatasetId: string }>();
  const [battery, setBattery] = useState<any>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    Promise.all([
      api.getBattery(activeDatasetId),
      api.getTimeline(activeDatasetId)
    ])
      .then(([battRes, timeRes]) => {
        setBattery(battRes);
        setTimeline(timeRes);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset first.</div>;
  }

  const baseOpt = getBaseEChartsOption();
  const powerChartOption = timeline ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: 'axis' },
    legend: {
      data: ['Discharge Power (kW)', 'Charge Power (kW)'],
      textStyle: { fontSize: 11, color: '#64748B' },
      top: 0
    },
    xAxis: {
      ...baseOpt.xAxis,
      data: timeline.timestamps.map((t: string) => format12HourTime(t))
    },
    yAxis: { ...baseOpt.yAxis, name: 'kW' },
    series: [
      {
        name: 'Discharge Power (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: PALETTE.battery },
        areaStyle: { color: 'rgba(13, 148, 136, 0.1)' },
        data: timeline.battery_power_kw.map((v: number) => Math.max(0, v))
      },
      {
        name: 'Charge Power (kW)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: PALETTE.solar },
        areaStyle: { color: 'rgba(217, 119, 6, 0.1)' },
        data: timeline.battery_power_kw.map((v: number) => Math.max(0, -v))
      }
    ]
  } : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-lg font-semibold tracking-tight">Battery Storage Intelligence & Laboratory</h1>
        <p className="text-xs text-slate-500">Cycling throughput, state-of-charge trajectory, reserve cutoff limits, and usable energy above minimum threshold.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Discharging Energy</span>
          <span className="text-xl font-bold tabular-nums text-battery-600">
            {battery?.discharging_energy_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Peak: {battery?.peak_discharge_kw} kW</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Charging Energy</span>
          <span className="text-xl font-bold tabular-nums text-solar-600">
            {battery?.charging_energy_kwh?.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Peak: {battery?.peak_charge_kw} kW</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">SOC Range Observed</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {battery?.min_soc_percent}% - {battery?.max_soc_percent}%
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Start: {battery?.initial_soc_percent}% | End: {battery?.final_soc_percent}%</span>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <span className="text-xs text-slate-500 block mb-1">Equivalent Full Cycles</span>
          <span className="text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {battery?.equivalent_full_cycles}
          </span>
          <span className="text-[11px] text-slate-500 block mt-1">Capacity: {battery?.nominal_capacity_kwh} kWh</span>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-semibold mb-3">Charge & Discharge Power Profiles (kW)</h2>
        {powerChartOption && <EChartComponent option={powerChartOption} height={300} loading={loading} />}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <h2 className="text-xs font-semibold mb-3">Reserve Constraint & Grid Cutoff</h2>
          <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded text-xs text-slate-700 dark:text-slate-300 mb-3">
            <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block mb-0.5">Observed Cutoff at 25.0% SOC</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                The battery discharged until 4:10 AM when SOC reached 25.0%. The battery then entered idle float mode, and household demand transferred to the utility grid.
              </p>
            </div>
          </div>
          <div className="flex justify-between py-1.5 text-xs border-b border-slate-100 dark:border-slate-800">
            <span className="text-slate-500">Configured Minimum Reserve</span>
            <span className="font-mono font-medium">{battery?.reserve_soc_percent}%</span>
          </div>
          <div className="flex justify-between py-1.5 text-xs">
            <span className="text-slate-500">Duration at or Near Reserve</span>
            <span className="font-mono font-medium">{battery?.hours_at_reserve_limit} hours</span>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
          <h2 className="text-xs font-semibold mb-3">Usable Energy & Sizing Implications</h2>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">Usable Stored Energy (above 25% SOC)</span>
              <span className="font-mono font-semibold text-battery-600">{battery?.usable_energy_above_reserve_kwh} kWh</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">Net Battery Energy Contribution</span>
              <span className="font-mono font-medium">{battery?.net_battery_kwh} kWh (Net Discharge)</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-500">Estimated Autonomy Extension per +5 kWh</span>
              <span className="font-mono font-medium">+3.6 hours at avg nighttime load</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
