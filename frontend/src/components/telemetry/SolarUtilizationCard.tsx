import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { EChartComponent } from '../charts/EChartComponent';
import { Tooltip } from '../common/Tooltip';

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

const sliceDefinitions: Record<string, { title: string; content: string; provenance?: 'Measured' | 'Calculated' | 'Estimated' }> = {
  Import: {
    title: 'Utility Grid Import',
    content: 'Electricity purchased from the TEI utility grid when solar and battery were insufficient.',
    provenance: 'Calculated'
  },
  Discharge: {
    title: 'Battery Discharge',
    content: 'Stored battery power discharged to supply household loads during evening or peak demand hours.',
    provenance: 'Calculated'
  },
  PV: {
    title: 'Direct Solar to Home',
    content: 'Solar electricity powering home appliances immediately as generated, with zero storage losses.',
    provenance: 'Calculated'
  },
  Charge: {
    title: 'Solar Stored in Battery',
    content: 'Surplus solar energy stored into your battery pack for use during the night.',
    provenance: 'Calculated'
  },
  Consumption: {
    title: 'Self-Consumed Solar',
    content: 'Solar energy absorbed directly by appliances without being stored or exported.',
    provenance: 'Calculated'
  }
};

export const SolarUtilizationCard: React.FC<SolarUtilizationCardProps> = ({
  consumptionTotalKwh = 0,
  consumptionBreakdown,
  productionTotalKwh = 0,
  productionBreakdown,
  dateLabel = '11/2026',
  onPrevMonth,
  onNextMonth
}) => {
  const [period, setPeriod] = useState<'M' | 'Y' | 'T'>('M');

  const emptyConsumption: UtilizationSlice[] = [
    { label: 'Import', kwh: 0, pct: 0, color: '#6366F1' },
    { label: 'Discharge', kwh: 0, pct: 0, color: '#06B6D4' },
    { label: 'PV', kwh: 0, pct: 0, color: '#10B981' }
  ];

  const emptyProduction: UtilizationSlice[] = [
    { label: 'Charge', kwh: 0, pct: 0, color: '#F59E0B' },
    { label: 'Consumption', kwh: 0, pct: 0, color: '#EAB308' }
  ];

  const rawConsSlices = consumptionBreakdown && consumptionBreakdown.length > 0 ? consumptionBreakdown : emptyConsumption;
  const rawProdSlices = productionBreakdown && productionBreakdown.length > 0 ? productionBreakdown : emptyProduction;

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
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-sm h-full flex flex-col justify-between interactive-card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <Tooltip
          title="Solar & Utilization Breakdown"
          content="Energy source origins for home consumption (grid, battery, solar), and the destination split for solar production (battery charging vs immediate appliance use)."
          position="bottom"
        >
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 cursor-help">Solar & Utilization</h3>
        </Tooltip>

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

      <div className="grid grid-cols-1 min-[440px]:grid-cols-2 gap-4 my-auto">
        <div className="flex flex-col items-center">
          <div className="w-full h-36">
            <EChartComponent option={consOption} height={144} />
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px]">
            {consSlices.map((s) => {
              const def = sliceDefinitions[s.label];
              return (
                <div key={s.label} className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                  {def ? (
                    <Tooltip
                      title={def.title}
                      content={def.content}
                      provenance={def.provenance}
                      position="top"
                      underline
                    >
                      <span className="text-slate-500 dark:text-slate-400">{s.label}</span>
                    </Tooltip>
                  ) : (
                    <span className="text-slate-500 dark:text-slate-400">{s.label}</span>
                  )}
                  <span className="font-semibold text-slate-700 dark:text-slate-200">{s.pct.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col items-center">
          <div className="w-full h-36">
            <EChartComponent option={prodOption} height={144} />
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px]">
            {prodSlices.map((s) => {
              const def = sliceDefinitions[s.label];
              return (
                <div key={s.label} className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                  {def ? (
                    <Tooltip
                      title={def.title}
                      content={def.content}
                      provenance={def.provenance}
                      position="top"
                      underline
                    >
                      <span className="text-slate-500 dark:text-slate-400">{s.label}</span>
                    </Tooltip>
                  ) : (
                    <span className="text-slate-500 dark:text-slate-400">{s.label}</span>
                  )}
                  <span className="font-semibold text-slate-700 dark:text-slate-200">{s.pct.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
