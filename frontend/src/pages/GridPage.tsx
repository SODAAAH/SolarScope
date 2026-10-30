import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption, PALETTE } from '../lib/theme';
import { format12HourTime, formatHourLabel12 } from '../lib/formatters';
import { MetricCard } from '../components/ui/MetricCard';
import { Zap, Clock, ShieldAlert } from 'lucide-react';
import type { ViewMode } from '../lib/terminology';

export const GridPage: React.FC = () => {
  const { activeDatasetId, viewMode } = useOutletContext<{
    activeDatasetId: string;
    viewMode: ViewMode;
  }>();
  const [grid, setGrid] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.getGrid(activeDatasetId)
      .then(setGrid)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset in the scope dropdown.</div>;
  }

  const baseOpt = getBaseEChartsOption();
  const hourlyChartOption = grid?.hourly_breakdown ? {
    ...baseOpt,
    tooltip: { ...baseOpt.tooltip, trigger: 'axis' },
    xAxis: {
      ...baseOpt.xAxis,
      data: grid.hourly_breakdown.map((h: any) => formatHourLabel12(h.hour))
    },
    yAxis: { ...baseOpt.yAxis, name: 'Bought from TEI (kWh)' },
    series: [
      {
        name: 'Electricity Bought from TEI',
        type: 'bar',
        barWidth: '60%',
        itemStyle: { color: PALETTE.grid, borderRadius: [4, 4, 0, 0] },
        data: grid.hourly_breakdown.map((h: any) => h.energy_kwh)
      }
    ]
  } : null;

  const totalImport = grid?.imported_energy_kwh ?? 0;
  const reserveCoincident = grid?.reserve_coincident_import_kwh ?? 0;
  const coincidentPct = totalImport > 0 ? (reserveCoincident / totalImport) * 100 : 0;
  const spikeKwh = Math.max(0, totalImport - reserveCoincident);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            {viewMode === 'simple' ? 'Electricity Bought from TEI' : 'Utility Grid Import & Dependence Analysis'}
          </h1>
          <p className="text-xs text-slate-500">
            {viewMode === 'simple'
              ? 'Find out when your home bought electricity from TEI and why it happened.'
              : 'Empirical examination of utility grid interaction episodes, peak demand, and reserve-coincident imports.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          termId="grid_import"
          value={totalImport.toFixed(2)}
          unit="kWh"
          viewMode={viewMode}
          icon={Zap}
          accentColor="coral"
          plainExplanation={`You bought ${totalImport.toFixed(1)} kWh of electricity from TEI across this period.`}
          subtext="Total utility exchange"
        />

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            {viewMode === 'simple' ? 'Reliance on TEI' : 'Grid Dependence Ratio'}
          </span>
          <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 dark:text-white">
            {((grid?.grid_dependence_ratio || 0) * 100).toFixed(1)} <span className="text-xs font-normal text-slate-500">%</span>
          </div>
          <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            {viewMode === 'simple' ? 'Percentage of your total home electricity that came from TEI.' : 'Integrated import energy divided by total home demand.'}
          </p>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            {viewMode === 'simple' ? 'Highest Rate Bought' : 'Peak Import Power'}
          </span>
          <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 dark:text-white">
            {(grid?.peak_import_kw || 0).toFixed(2)} <span className="text-xs font-normal text-slate-500">kW</span>
          </div>
          <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            Reached at {grid?.peak_import_time_12h || format12HourTime(grid?.peak_import_time) || 'N/A'}.
          </p>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-1">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
            {viewMode === 'simple' ? 'Bought When Battery Empty' : 'Reserve Coincident Import'}
          </span>
          <div className="text-2xl font-bold font-mono tabular-nums text-orange-600 dark:text-orange-400">
            {reserveCoincident.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
          </div>
          <p className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 dark:border-slate-800">
            {coincidentPct.toFixed(1)}% of grid purchases occurred while battery was resting at reserve limit.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
            {viewMode === 'simple' ? 'When Did Your Home Buy Electricity from TEI?' : 'Hourly Utility Import Histogram'}
          </h2>
          <span className="text-[11px] font-mono text-slate-400">12 AM to 11 PM</span>
        </div>
        {hourlyChartOption && <EChartComponent option={hourlyChartOption} height={300} loading={loading} />}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-500" />
            <span>{viewMode === 'simple' ? 'Electricity Purchase Timetable' : 'Grid Ingress Events & Timing'}</span>
          </h2>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">First Substantial Import (&gt;100 W)</span>
              <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                {grid?.first_import_time_12h || format12HourTime(grid?.first_import_time) || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500">Last Substantial Import (&gt;100 W)</span>
              <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                {grid?.last_import_time_12h || format12HourTime(grid?.last_import_time) || 'N/A'}
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-500">Daytime Grid Purchases (While Sun Was Up)</span>
              <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                {grid?.daylight_import_kwh ?? 0} kWh
              </span>
            </div>
          </div>
        </div>

        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-orange-500" />
            <span>Why Did Your House Buy Electricity from TEI?</span>
          </h2>
          <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed space-y-2">
            <p>
              Of the <strong>{totalImport.toFixed(2)} kWh</strong> bought from TEI, <strong>{reserveCoincident.toFixed(2)} kWh ({coincidentPct.toFixed(1)}%)</strong> happened while your battery was resting at its minimum reserve limit (around 25%). During these hours, your house had no stored solar power left, so electricity came directly from TEI.
            </p>
            {spikeKwh > 0 && (
              <p>
                The remaining <strong>{spikeKwh.toFixed(2)} kWh</strong> occurred during sudden spikes in appliance usage that temporarily exceeded what your solar panels and battery could provide at that exact second.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
