import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { EChartComponent } from '../charts/EChartComponent';

interface UtilizationSlice {
  label: string;
  kwh: number;
  pct: number;
  color: string;
}

interface SolarUtilizationCardProps {
  consumptionTotalKwh?: number;
  consumptionBreakdown?: UtilizationSlice[];
  productionTotalKwh?: number;
  productionBreakdown?: UtilizationSlice[];
  dateLabel?: string;
  onPrevMonth?: () => void;
  onNextMonth?: () => void;
}

export const SolarUtilizationCard: React.FC<SolarUtilizationCardProps> = ({
  consumptionTotalKwh = 371.10,
  consumptionBreakdown,
  productionTotalKwh = 270.80,
  productionBreakdown,
  dateLabel = '11/2026',
  onPrevMonth,
  onNextMonth
}) => {
  const [period, setPeriod] = useState<'M' | 'Y' | 'T'>('M');

  const defaultConsumption: UtilizationSlice[] = [
    { label: 'Import', kwh: 110.0, pct: 29.6, color: '#6366F1' },
    { label: 'Discharge', kwh: 119.79, pct: 32.3, color: '#06B6D4' },
    { label: 'PV', kwh: 141.29, pct: 38.1, color: '#10B981' }
  ];

  const defaultProduction: UtilizationSlice[] = [
    { label: 'Charge', kwh: 128.70, pct: 47.7, color: '#F59E0B' },
    { label: 'Consumption', kwh: 141.29, pct: 52.3, color: '#EAB308' }
  ];

  const rawConsSlices = consumptionBreakdown && consumptionBreakdown.length > 0 ? consumptionBreakdown : defaultConsumption;
  const rawProdSlices = productionBreakdown && productionBreakdown.length > 0 ? productionBreakdown : defaultProduction;

  const normalizeSlices = (slices: UtilizationSlice[]): UtilizationSlice[] => {
    const total = slices.reduce((acc, s) => acc + s.kwh, 0);
    if (total <= 0) return slices;
    return slices.map((s) => ({
      ...s,
      pct: (s.kwh / total) * 100
    }));
  };

  const consSlices = normalizeSlices(rawConsSlices);
  const prodSlices = normalizeSlices(rawProdSlices);

  const makeDonutOption = (title: string, totalKwh: number, slices: UtilizationSlice[]) => {
    return {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} kWh ({d}%)',
        textStyle: { fontSize: 11 }
      },
      series: [
        {
          name: title,
          type: 'pie',
          radius: ['52%', '75%'],
          center: ['50%', '50%'],
          avoidLabelOverlap: false,
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 11,
              fontWeight: 'bold',
              formatter: '{b}\n{d}%'
            }
          },
          labelLine: {
            show: false
          },
          data: slices.map((s) => ({
            value: s.kwh,
            name: s.label,
            itemStyle: { color: s.color }
          }))
        }
      ],
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: '42%',
          style: {
            text: title,
            fill: '#64748B',
            fontSize: 10,
            fontWeight: 500
          }
        },
        {
          type: 'text',
          left: 'center',
          top: '52%',
          style: {
            text: `${totalKwh.toFixed(1)}`,
            fill: '#0F172A',
            fontSize: 13,
            fontWeight: 'bold'
          }
        }
      ]
    };
  };

  const consOption = makeDonutOption('Consumption', consumptionTotalKwh, consSlices);
  const prodOption = makeDonutOption('Production', productionTotalKwh, prodSlices);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm h-full flex flex-col justify-between interactive-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Solar & Utilization</h3>

        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-md text-[11px] font-medium">
            {(['M', 'Y', 'T'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-0.5 rounded ${
                  period === p
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 text-[11px] font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded-md">
            <button
              onClick={onPrevMonth}
              className="p-0.5 hover:text-slate-900 dark:hover:text-white"
            >
              <ChevronLeft className="h-3 w-3" />
            </button>
            <span className="font-mono text-[11px]">{dateLabel}</span>
            <button
              onClick={onNextMonth}
              className="p-0.5 hover:text-slate-900 dark:hover:text-white"
            >
              <ChevronRight className="h-3 w-3" />
            </button>
            <Calendar className="h-3 w-3 text-slate-400 ml-1" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 my-auto">
        <div className="flex flex-col items-center">
          <div className="w-full h-36">
            <EChartComponent option={consOption} height={144} />
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px]">
            {consSlices.map((s) => (
              <div key={s.label} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                <span className="text-slate-500 dark:text-slate-400">{s.label}</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">{s.pct.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-center">
          <div className="w-full h-36">
            <EChartComponent option={prodOption} height={144} />
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px]">
            {prodSlices.map((s) => (
              <div key={s.label} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                <span className="text-slate-500 dark:text-slate-400">{s.label}</span>
                <span className="font-semibold text-slate-700 dark:text-slate-200">{s.pct.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
