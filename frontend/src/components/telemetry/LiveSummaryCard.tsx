import React from 'react';
import { Zap, Home, CloudSun } from 'lucide-react';

interface LiveSummaryCardProps {
  accumulativeProductionKwh?: number;
  accumulativeConsumptionKwh?: number;
  dailyProductionKwh?: number;
  weatherTempC?: number;
}

export const LiveSummaryCard: React.FC<LiveSummaryCardProps> = ({
  accumulativeProductionKwh = 270.80,
  accumulativeConsumptionKwh = 371.10,
  dailyProductionKwh = 15.90,
  weatherTempC = 28
}) => {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm flex flex-col justify-between">
      <div>
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-5">Summary</h3>

        <div className="space-y-4">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-blue-500/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400">Accumulative production</div>
              <div className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {accumulativeProductionKwh.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-sky-500/10 dark:bg-sky-500/20 text-sky-600 dark:text-sky-400 flex items-center justify-center shrink-0">
              <Home className="h-5 w-5" />
            </div>
            <div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400">Accumulative consumption</div>
              <div className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {accumulativeConsumptionKwh.toFixed(2)} <span className="text-xs font-normal text-slate-500">kWh</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 grid grid-cols-2 gap-4">
        <div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400">Daily Production</div>
          <div className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
            {dailyProductionKwh.toFixed(2)} <span className="text-[11px] font-normal text-slate-500">kWh</span>
          </div>
        </div>

        <div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400">Weather</div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <CloudSun className="h-4 w-4 text-amber-500" />
            <span className="text-base font-bold text-slate-900 dark:text-slate-100">{weatherTempC.toFixed(0)} ℃</span>
          </div>
        </div>
      </div>
    </div>
  );
};

