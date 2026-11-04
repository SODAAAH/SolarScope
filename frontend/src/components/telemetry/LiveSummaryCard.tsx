import React from 'react';
import { Zap, Home, CloudSun } from 'lucide-react';

interface LiveSummaryCardProps {
  accumulativeProductionKwh?: number;
  accumulativeConsumptionKwh?: number;
  dailyProductionKwh?: number;
  dailyConsumptionKwh?: number;
  selfConsumptionRate?: number;
  weatherTempC?: number;
}

export const LiveSummaryCard: React.FC<LiveSummaryCardProps> = ({
  accumulativeProductionKwh = 270.80,
  accumulativeConsumptionKwh = 371.10,
  dailyProductionKwh = 15.90,
  dailyConsumptionKwh = 21.40,
  selfConsumptionRate = 84.5,
  weatherTempC = 28
}) => {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm h-full flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Summary</h3>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
            Telemetry
          </span>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3.5 p-3 rounded-lg bg-slate-50/60 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800/60">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Accumulative production</div>
              <div className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {accumulativeProductionKwh.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3.5 p-3 rounded-lg bg-slate-50/60 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800/60">
            <div className="w-10 h-10 rounded-lg bg-sky-500/10 dark:bg-sky-500/20 text-sky-600 dark:text-sky-400 flex items-center justify-center shrink-0">
              <Home className="h-5 w-5" />
            </div>
            <div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Accumulative consumption</div>
              <div className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {accumulativeConsumptionKwh.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800/80">
        <div className="grid grid-cols-2 gap-3">
          <div className="p-2.5 rounded-lg bg-slate-50/40 dark:bg-slate-800/20 border border-slate-100 dark:border-slate-800/40">
            <div className="text-[11px] text-slate-500 dark:text-slate-400">Daily Production</div>
            <div className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-0.5">
              {dailyProductionKwh.toFixed(2)} <span className="text-[10px] font-normal text-slate-500">kWh</span>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50/40 dark:bg-slate-800/20 border border-slate-100 dark:border-slate-800/40">
            <div className="text-[11px] text-slate-500 dark:text-slate-400">Daily Consumption</div>
            <div className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-0.5">
              {dailyConsumptionKwh.toFixed(2)} <span className="text-[10px] font-normal text-slate-500">kWh</span>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50/40 dark:bg-slate-800/20 border border-slate-100 dark:border-slate-800/40">
            <div className="text-[11px] text-slate-500 dark:text-slate-400">Self-Consumption</div>
            <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
              {selfConsumptionRate.toFixed(1)}%
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50/40 dark:bg-slate-800/20 border border-slate-100 dark:border-slate-800/40">
            <div className="text-[11px] text-slate-500 dark:text-slate-400">Weather</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <CloudSun className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              <span className="text-sm font-bold text-slate-900 dark:text-slate-100">{weatherTempC.toFixed(0)} ℃</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
