import { Tooltip } from '../components/common/Tooltip';
import React, { useState, useEffect } from 'react';
import { useOutletContext, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import type { LiveFlowResponse, DailySummaryItem } from '../lib/api';
import { EChartComponent } from '../components/charts/EChartComponent';
import { getBaseEChartsOption } from '../lib/theme';
import {
  AlertCircle,
  Calendar,
  Download,
  ChevronLeft,
  ChevronRight,
  Loader2
} from 'lucide-react';
import { formatDateMMDDYYYY } from '../lib/formatters';
import { LiveFlowGraph } from '../components/telemetry/LiveFlowGraph';
import { LiveSummaryCard } from '../components/telemetry/LiveSummaryCard';
import { SolarUtilizationCard } from '../components/telemetry/SolarUtilizationCard';
import type { ViewMode } from '../lib/terminology';

export const OverviewPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{
    activeDatasetId: string;
    viewMode: ViewMode;
  }>();

  const [summary, setSummary] = useState<any>(() => {
    try {
      const saved = sessionStorage.getItem(`solarscope_cached_summary_${activeDatasetId || 'all'}`);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [timeline, setTimeline] = useState<any>(null);
  const [liveFlow, setLiveFlow] = useState<LiveFlowResponse | null>(null);
  const [dailySummaries, setDailySummaries] = useState<DailySummaryItem[]>(() => {
    try {
      const saved = sessionStorage.getItem('solarscope_cached_daily');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState<boolean>(() => {
    try {
      return !sessionStorage.getItem(`solarscope_cached_summary_${activeDatasetId || 'all'}`);
    } catch {
      return true;
    }
  });
  const [error, setError] = useState<string | null>(null);
  const [historyPeriod, setHistoryPeriod] = useState<'M' | 'Y' | 'T'>('M');
  const [selectedHistoryMonth, setSelectedHistoryMonth] = useState<string>(() => {
    try {
      const saved = sessionStorage.getItem('solarscope_cached_daily');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed[parsed.length - 1].date.slice(0, 7);
        }
      }
    } catch {}
    return '2026-11';
  });
  const [powerProfileDate, setPowerProfileDate] = useState<string>(() => {
    try {
      const saved = sessionStorage.getItem('solarscope_cached_daily');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed[parsed.length - 1].date;
        }
      }
    } catch {}
    return '2026-11-04';
  });
  const [timelineLoading, setTimelineLoading] = useState<boolean>(false);
  const navigate = useNavigate();

  const fetchOverviewData = () => {
    if (!activeDatasetId) return;
    if (!summary) {
      setLoading(true);
    }
    setError(null);

    api.getSummary(activeDatasetId)
      .then((sumRes) => {
        if (sumRes) {
          setSummary(sumRes);
          setLoading(false);
          try {
            sessionStorage.setItem(`solarscope_cached_summary_${activeDatasetId}`, JSON.stringify(sumRes));
          } catch {}
        }
      })
      .catch((err) => {
        if (!summary) {
          setError(err.message || 'Failed to load system metrics');
        }
      })
      .finally(() => {
        setLoading(false);
      });

    api.getHistoricalDaily()
      .then((dailyRes) => {
        if (dailyRes && dailyRes.length > 0) {
          setDailySummaries(dailyRes);
          try {
            sessionStorage.setItem('solarscope_cached_daily', JSON.stringify(dailyRes));
          } catch {}
          if (!powerProfileDate || !dailyRes.some(d => d.date === powerProfileDate)) {
            setPowerProfileDate(dailyRes[dailyRes.length - 1].date);
          }
          const latestMonth = dailyRes[dailyRes.length - 1].date.slice(0, 7);
          setSelectedHistoryMonth((prev) => (prev ? prev : latestMonth));
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchOverviewData();
  }, [activeDatasetId]);

  useEffect(() => {
    if (!activeDatasetId || !powerProfileDate) return;
    setTimelineLoading(true);
    api.getTimeline(activeDatasetId, powerProfileDate)
      .then((res) => {
        if (res) setTimeline(res);
      })
      .catch(console.error)
      .finally(() => {
        setTimelineLoading(false);
      });
  }, [activeDatasetId, powerProfileDate]);

  const availableDates = dailySummaries.map((d) => d.date);
  const currentDateIndex = availableDates.indexOf(powerProfileDate);

  const handlePrevDate = () => {
    if (currentDateIndex > 0) {
      setPowerProfileDate(availableDates[currentDateIndex - 1]);
    }
  };

  const handleNextDate = () => {
    if (currentDateIndex < availableDates.length - 1) {
      setPowerProfileDate(availableDates[currentDateIndex + 1]);
    }
  };

  const isFirstDate = currentDateIndex <= 0;
  const isLastDate = currentDateIndex >= availableDates.length - 1 || currentDateIndex === -1;

  if (!activeDatasetId) {
    return (
      <div className="max-w-xl mx-auto mt-20 p-8 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 text-center">
        <h2 className="text-base font-semibold mb-2">No Active Dataset</h2>
        <p className="text-xs text-slate-500 mb-6">
          Import your inverter export files in the Historical Library or connect Deye Cloud to inspect energy analytics.
        </p>
        <button
          onClick={() => navigate('/library')}
          className="bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-medium px-4 py-2 rounded-md transition-colors"
        >
          Go to Data Library
        </button>
      </div>
    );
  }

  if (loading && !summary && !liveFlow) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="text-xs text-slate-500 font-mono">Calculating verified energy metrics...</div>
      </div>
    );
  }

  if (error && !summary && !liveFlow) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-md text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  const baseOpt = getBaseEChartsOption();

  const powerProfileOption = timeline ? {
    ...baseOpt,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      textStyle: { fontSize: 11 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return '';
        const timeLabel = params[0].axisValueLabel || params[0].name;
        let res = `<div class="font-sans text-xs font-semibold pb-1 mb-1 border-b border-slate-200 dark:border-slate-700">${timeLabel} (${formatDateMMDDYYYY(powerProfileDate)})</div>`;
        params.forEach((p: any) => {
          if (p.value !== null && p.value !== undefined) {
            const unit = p.seriesName === 'SOC' ? '%' : 'kW';
            res += `<div class="flex items-center justify-between gap-4 text-xs font-sans">
              <span style="color:${p.color}">● ${p.seriesName}</span>
              <span class="font-mono font-medium">${Number(p.value).toFixed(2)}${unit}</span>
            </div>`;
          }
        });
        return res;
      }
    },
    legend: {
      data: ['Solar (PV)', 'Grid', 'Battery', 'Consumption', 'SOC'],
      textStyle: { fontSize: 11, color: '#64748B' },
      top: 2,
      right: 8
    },
    grid: {
      left: '3%',
      right: '4%',
      top: '16%',
      bottom: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: timeline.timestamps_24h || (timeline.timestamps ? timeline.timestamps.map((t: string) => t.includes(' ') ? t.split(' ')[1].slice(0, 5) : t) : []),
      axisLabel: {
        interval: (index: number) => index % 36 === 0,
        color: '#94A3B8',
        fontSize: 10
      },
      axisLine: { lineStyle: { color: '#CBD5E1' } },
      axisTick: { alignWithLabel: true }
    },
    yAxis: [
      {
        ...baseOpt.yAxis,
        name: 'kW',
        position: 'left',
        axisLabel: { fontSize: 10, color: '#94A3B8' }
      },
      {
        type: 'value',
        name: '%',
        min: 0,
        max: 100,
        position: 'right',
        splitLine: { show: false },
        axisLabel: { formatter: '{value}%', fontSize: 10, color: '#94A3B8' }
      }
    ],
    series: [
      {
        name: 'Solar (PV)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#F59E0B' },
        data: timeline.pv_power_kw
      },
      {
        name: 'Grid',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#6366F1' },
        data: timeline.grid_power_kw
      },
      {
        name: 'Battery',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#06B6D4' },
        data: timeline.battery_power_kw
      },
      {
        name: 'Consumption',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#10B981' },
        data: timeline.load_power_kw
      },
      {
        name: 'SOC',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#3B82F6', type: 'dashed' },
        data: timeline.soc_percent
      }
    ]
  } : null;

  const availableMonths = Array.from(new Set(dailySummaries.map((d) => d.date.slice(0, 7)))).sort();
  const currentMonthIdx = availableMonths.indexOf(selectedHistoryMonth);

  const handlePrevMonth = () => {
    if (currentMonthIdx > 0) {
      setSelectedHistoryMonth(availableMonths[currentMonthIdx - 1]);
    }
  };

  const handleNextMonth = () => {
    if (currentMonthIdx < availableMonths.length - 1) {
      setSelectedHistoryMonth(availableMonths[currentMonthIdx + 1]);
    }
  };

  const [selYearStr, selMonthStr] = (selectedHistoryMonth || '2026-11').split('-');
  const selYear = parseInt(selYearStr, 10) || 2026;
  const selMonth = parseInt(selMonthStr, 10) || 11;
  const daysInSelMonth = new Date(selYear, selMonth, 0).getDate();
  const monthDays = Array.from({ length: daysInSelMonth }, (_, i) => i + 1);

  const currentMonthSummaries = dailySummaries.filter((d) => d.date.startsWith(selectedHistoryMonth));
  const daySummaryMap = new Map<number, DailySummaryItem>();
  currentMonthSummaries.forEach((d) => {
    try {
      const parts = d.date.split('-');
      if (parts.length === 3) {
        const dayNum = parseInt(parts[2], 10);
        daySummaryMap.set(dayNum, d);
      }
    } catch {
    }
  });

  const selectedHistoryMonthDisplay = `${String(selMonth).padStart(2, '0')}/${selYear}`;

  const currentMonthPvTotal = currentMonthSummaries.reduce((acc, d) => acc + d.pv_kwh, 0);
  const currentMonthLoadTotal = currentMonthSummaries.reduce((acc, d) => acc + d.load_kwh, 0);
  const currentMonthImportTotal = currentMonthSummaries.reduce((acc, d) => acc + d.grid_import_kwh, 0);
  const currentMonthDischargeTotal = currentMonthSummaries.reduce((acc, d) => acc + d.battery_discharge_kwh, 0);
  const currentMonthChargeTotal = currentMonthSummaries.reduce((acc, d) => acc + d.battery_charge_kwh, 0);
  const currentMonthDirectPv = Math.max(0, currentMonthLoadTotal - currentMonthImportTotal - currentMonthDischargeTotal);

  const monthConsBreakdown = [
    { label: 'Import', kwh: currentMonthImportTotal, pct: currentMonthLoadTotal > 0 ? (currentMonthImportTotal / currentMonthLoadTotal) * 100 : 33.3, color: '#6366F1' },
    { label: 'Discharge', kwh: currentMonthDischargeTotal, pct: currentMonthLoadTotal > 0 ? (currentMonthDischargeTotal / currentMonthLoadTotal) * 100 : 33.3, color: '#06B6D4' },
    { label: 'PV', kwh: currentMonthDirectPv, pct: currentMonthLoadTotal > 0 ? (currentMonthDirectPv / currentMonthLoadTotal) * 100 : 33.4, color: '#10B981' }
  ];

  const monthProdBreakdown = [
    { label: 'Charge', kwh: currentMonthChargeTotal, pct: (currentMonthChargeTotal + currentMonthDirectPv) > 0 ? (currentMonthChargeTotal / (currentMonthChargeTotal + currentMonthDirectPv)) * 100 : 50, color: '#F59E0B' },
    { label: 'Consumption', kwh: currentMonthDirectPv, pct: (currentMonthChargeTotal + currentMonthDirectPv) > 0 ? (currentMonthDirectPv / (currentMonthChargeTotal + currentMonthDirectPv)) * 100 : 50, color: '#EAB308' }
  ];

  const todaySummary = dailySummaries.length > 0 ? dailySummaries[dailySummaries.length - 1] : null;

  const historyOption = {
    ...baseOpt,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      textStyle: { fontSize: 11 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return '';
        const day = params[0].axisValueLabel || params[0].name;
        let res = `<div class="font-sans text-xs font-semibold pb-1 mb-1 border-b border-slate-200 dark:border-slate-700">${selectedHistoryMonthDisplay} - Day ${day}</div>`;
        let hasData = false;
        params.forEach((p: any) => {
          if (p.value !== null && p.value !== undefined && p.value !== 0) {
            hasData = true;
            const val = Math.abs(Number(p.value)).toFixed(2);
            res += `<div class="flex items-center justify-between gap-4 text-xs font-sans">
              <span style="color:${p.color}">● ${p.seriesName}</span>
              <span class="font-mono font-medium">${val} kWh</span>
            </div>`;
          }
        });
        if (!hasData) {
          res += `<div class="text-xs text-slate-400 font-sans">No recorded data</div>`;
        }
        return res;
      }
    },
    legend: {
      data: ['Production', 'Discharge', 'Purchased', 'Consumption', 'Charge', 'Grid Feed-in'],
      textStyle: { fontSize: 10, color: '#64748B' },
      top: 2,
      itemGap: 10,
      itemWidth: 10,
      itemHeight: 8
    },
    grid: {
      left: '3%',
      right: '4%',
      top: '18%',
      bottom: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: monthDays.map((d) => d.toString()),
      axisLabel: {
        interval: (index: number) => index === 0 || ((index + 1) % 5 === 0 && monthDays.length - 1 - index >= 2) || index === monthDays.length - 1,
        fontSize: 10,
        color: '#64748B'
      },
      axisLine: { lineStyle: { color: '#CBD5E1' } },
      axisTick: { alignWithLabel: true }
    },
    yAxis: {
      ...baseOpt.yAxis,
      name: 'kWh',
      nameTextStyle: { fontSize: 10, color: '#64748B' },
      axisLabel: { fontSize: 10, color: '#64748B' },
      splitLine: { lineStyle: { color: '#E2E8F0', type: 'dashed' } }
    },
    series: [
      {
        name: 'Production',
        type: 'bar',
        stack: 'positive',
        barMaxWidth: 16,
        itemStyle: { color: '#10B981', borderRadius: [2, 2, 0, 0] },
        data: monthDays.map((d) => {
          const item = daySummaryMap.get(d);
          return item ? item.pv_kwh : 0;
        })
      },
      {
        name: 'Discharge',
        type: 'bar',
        stack: 'positive',
        barMaxWidth: 16,
        itemStyle: { color: '#06B6D4' },
        data: monthDays.map((d) => {
          const item = daySummaryMap.get(d);
          return item ? item.battery_discharge_kwh : 0;
        })
      },
      {
        name: 'Purchased',
        type: 'bar',
        stack: 'positive',
        barMaxWidth: 16,
        itemStyle: { color: '#6366F1' },
        data: monthDays.map((d) => {
          const item = daySummaryMap.get(d);
          return item ? item.grid_import_kwh : 0;
        })
      },
      {
        name: 'Consumption',
        type: 'bar',
        stack: 'negative',
        barMaxWidth: 16,
        itemStyle: { color: '#F59E0B' },
        data: monthDays.map((d) => {
          const item = daySummaryMap.get(d);
          return item ? -Math.abs(item.load_kwh) : 0;
        })
      },
      {
        name: 'Charge',
        type: 'bar',
        stack: 'negative',
        barMaxWidth: 16,
        itemStyle: { color: '#3B82F6' },
        data: monthDays.map((d) => {
          const item = daySummaryMap.get(d);
          return item ? -Math.abs(item.battery_charge_kwh) : 0;
        })
      },
      {
        name: 'Grid Feed-in',
        type: 'bar',
        stack: 'negative',
        barMaxWidth: 16,
        itemStyle: { color: '#EF4444', borderRadius: [0, 0, 2, 2] },
        data: monthDays.map((d) => {
          const item = daySummaryMap.get(d);
          return item ? -Math.abs(item.grid_export_kwh || 0) : 0;
        })
      }
    ]
  };

  const sol = summary?.solar || {};
  const solarKwh = summary?.balance?.pv_kwh ?? sol.total_generation_kwh ?? 0;
  const loadKwh = summary?.balance?.household_demand_kwh ?? summary?.consumption?.total_consumption_kwh ?? 0;
  const allDailyPvTotal = dailySummaries.reduce((acc, d) => acc + d.pv_kwh, 0);
  const allDailyLoadTotal = dailySummaries.reduce((acc, d) => acc + d.load_kwh, 0);
  const hasRealFlow = Boolean(liveFlow && (liveFlow.is_live || liveFlow.data_source === 'demo' || liveFlow.data_source === 'cached'));

  const accumProdKwh = allDailyPvTotal > 0
    ? allDailyPvTotal
    : (solarKwh > 0 ? solarKwh : (hasRealFlow ? (liveFlow?.summary.accumulative_production_kwh ?? 0) : 0));
  const accumConsKwh = allDailyLoadTotal > 0
    ? allDailyLoadTotal
    : (loadKwh > 0 ? loadKwh : (hasRealFlow ? (liveFlow?.summary.accumulative_consumption_kwh ?? 0) : 0));
  const dailyProdKwh = todaySummary
    ? todaySummary.pv_kwh
    : (activeDatasetId !== 'all' ? solarKwh : (hasRealFlow ? (liveFlow?.summary.daily_production_kwh ?? 0) : 0));
  const dailyConsKwh = todaySummary
    ? todaySummary.load_kwh
    : (activeDatasetId !== 'all' ? loadKwh : 0);

  const balanceSelfConsRaw = summary?.balance?.solar_self_consumption_ratio;
  const balanceSelfConsPct = typeof balanceSelfConsRaw === 'number'
    ? (balanceSelfConsRaw <= 1 ? balanceSelfConsRaw * 100 : balanceSelfConsRaw)
    : 0;
  const selfConsPct = todaySummary && todaySummary.pv_kwh > 0
    ? Math.min(100, Math.max(0, ((todaySummary.pv_kwh - (todaySummary.grid_export_kwh || 0)) / todaySummary.pv_kwh) * 100))
    : balanceSelfConsPct;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-8">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-stretch">
            <div className="md:col-span-12 lg:col-span-5 flex flex-col card-stagger-1">
              <LiveFlowGraph
                initialData={liveFlow}
                onFlowUpdate={setLiveFlow}
                onRefreshRequested={fetchOverviewData}
              />
            </div>

            <div className="md:col-span-6 lg:col-span-3 flex flex-col card-stagger-2">
              <LiveSummaryCard
                accumulativeProductionKwh={accumProdKwh}
                accumulativeConsumptionKwh={accumConsKwh}
                dailyProductionKwh={dailyProdKwh}
                dailyConsumptionKwh={dailyConsKwh}
                selfConsumptionRate={selfConsPct}
                weatherTempC={liveFlow?.summary.weather_temp_c ?? 28}
              />
            </div>

            <div className="md:col-span-6 lg:col-span-4 flex flex-col card-stagger-3">
              <SolarUtilizationCard
                consumptionTotalKwh={currentMonthLoadTotal > 0 ? currentMonthLoadTotal : (hasRealFlow ? (liveFlow?.utilization?.consumption_total_kwh ?? 0) : 0)}
                consumptionBreakdown={currentMonthLoadTotal > 0 ? monthConsBreakdown : (hasRealFlow ? liveFlow?.utilization?.consumption_breakdown : undefined)}
                productionTotalKwh={currentMonthPvTotal > 0 ? currentMonthPvTotal : (hasRealFlow ? (liveFlow?.utilization?.production_total_kwh ?? 0) : 0)}
                productionBreakdown={currentMonthPvTotal > 0 ? monthProdBreakdown : (hasRealFlow ? liveFlow?.utilization?.production_breakdown : undefined)}
                dateLabel={selectedHistoryMonthDisplay}
                onPrevMonth={handlePrevMonth}
                onNextMonth={handleNextMonth}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs card-stagger-4 interactive-card">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-2">
                  <Tooltip
                    title="24-Hour Power Profile"
                    content="High-resolution time series of solar generation, battery power and state-of-charge, grid power exchange, and total household consumption."
                    position="bottom"
                  >
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 cursor-help">Power Profile</h3>
                  </Tooltip>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">24-Hour</span>
                  {timelineLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-600" />}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(timeline, null, 2)], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `power_profile_${powerProfileDate || 'data'}.json`;
                      a.click();
                    }}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>Export</span>
                  </button>

                  <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5 border border-slate-200 dark:border-slate-700 text-xs">
                    <button
                      type="button"
                      onClick={handlePrevDate}
                      disabled={isFirstDate}
                      className="p-1 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-600 dark:text-slate-300 disabled:opacity-30 disabled:hover:bg-transparent"
                      title="Previous Day"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>

                    <div className="relative flex items-center px-1">
                      <select
                        value={powerProfileDate}
                        onChange={(e) => setPowerProfileDate(e.target.value)}
                        className="bg-transparent text-slate-800 dark:text-slate-200 font-mono text-xs py-0.5 pl-1 pr-6 cursor-pointer focus:outline-none appearance-none"
                      >
                        {availableDates.map((dateStr) => (
                          <option key={dateStr} value={dateStr} className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 font-mono">
                            {formatDateMMDDYYYY(dateStr)}
                          </option>
                        ))}
                      </select>
                      <Calendar className="h-3 w-3 text-slate-400 absolute right-2 pointer-events-none" />
                    </div>

                    <button
                      type="button"
                      onClick={handleNextDate}
                      disabled={isLastDate}
                      className="p-1 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-600 dark:text-slate-300 disabled:opacity-30 disabled:hover:bg-transparent"
                      title="Next Day"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
              {powerProfileOption && <EChartComponent option={powerProfileOption} height={280} />}
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs card-stagger-5 interactive-card">
              <div className="flex items-center justify-between mb-3">
                <Tooltip
                  title="Generation & Usage History"
                  content="Stacked daily historical breakdown comparing rooftop solar generation, battery discharge/charge cycling, utility grid import, and household load."
                  position="bottom"
                >
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 cursor-help">Generation & Usage History</h3>
                </Tooltip>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const csv = dailySummaries.map((d) => `${d.date},${d.pv_kwh},${d.load_kwh},${d.grid_import_kwh},${d.battery_discharge_kwh}`).join('\n');
                      const blob = new Blob([`date,pv_kwh,load_kwh,grid_kwh,battery_kwh\n${csv}`], { type: 'text/csv' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'generation_usage_history.csv';
                      a.click();
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded transition-colors"
                  >
                    <Download className="h-3 w-3" />
                    <span>Export</span>
                  </button>

                  <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded text-[11px] font-medium">
                    {(['M', 'Y', 'T'] as const).map((p) => (
                      <button
                        key={p}
                        onClick={() => setHistoryPeriod(p)}
                        className={`px-1.5 py-0.5 rounded ${
                          historyPeriod === p
                            ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold'
                            : 'text-slate-500 hover:text-slate-800'
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-1 text-[11px] font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
                    <button
                      type="button"
                      onClick={handlePrevMonth}
                      disabled={currentMonthIdx <= 0}
                      className="p-0.5 hover:text-slate-900 dark:hover:text-white disabled:opacity-30 disabled:hover:text-slate-500 cursor-pointer"
                    >
                      <ChevronLeft className="h-3 w-3" />
                    </button>
                    <span className="font-mono">{selectedHistoryMonthDisplay}</span>
                    <button
                      type="button"
                      onClick={handleNextMonth}
                      disabled={currentMonthIdx >= availableMonths.length - 1}
                      className="p-0.5 hover:text-slate-900 dark:hover:text-white disabled:opacity-30 disabled:hover:text-slate-500 cursor-pointer"
                    >
                      <ChevronRight className="h-3 w-3" />
                    </button>
                    <Calendar className="h-3 w-3 text-slate-400 ml-1" />
                  </div>
                </div>
              </div>
              <EChartComponent option={historyOption} height={280} />
            </div>
          </div>
    </div>
  );
};
