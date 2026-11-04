import React, { useState, useEffect } from 'react';
import { Sun, Zap, Battery, Home, ShieldCheck, RefreshCw, CheckCircle2, ChevronDown } from 'lucide-react';
import type { LiveFlowResponse } from '../../lib/api';
import { api } from '../../lib/api';
import { format12HourTime } from '../../lib/formatters';

interface LiveFlowGraphProps {
  initialData?: LiveFlowResponse | null;
  onRefreshRequested?: () => void;
}

export const LiveFlowGraph: React.FC<LiveFlowGraphProps> = ({ initialData, onRefreshRequested }) => {
  const [data, setData] = useState<LiveFlowResponse | null>(initialData || null);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [dataMode, setDataMode] = useState<'plant' | 'live'>('plant');
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(15);

  const fetchFlowData = async () => {
    setLoading(true);
    try {
      const res = await api.getDeyeLiveFlow();
      if (res && res.success) {
        setData(res);
      }
    } catch {
    } finally {
      setLoading(false);
      setSecondsUntilRefresh(15);
      if (onRefreshRequested) {
        onRefreshRequested();
      }
    }
  };

  useEffect(() => {
    if (initialData) {
      setData(initialData);
    } else {
      fetchFlowData();
    }
  }, [initialData]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      setSecondsUntilRefresh((prev) => {
        if (prev <= 1) {
          fetchFlowData();
          return 15;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const nodes = data?.nodes || {
    solar: { power_w: 0.0, power_kw: 0.0, is_active: false },
    battery: { soc_percent: 63, power_w: 1210, power_kw: 1.21, state: 'DISCHARGING', is_charging: false, is_discharging: true },
    inverter: { status: 'OPERATIONAL', throughput_w: 1210, throughput_kw: 1.21 },
    grid: { power_w: 10, power_kw: 0.01, status_label: 'On grid', state: 'IMPORT', is_importing: true, is_exporting: false },
    load: { power_w: 10, power_kw: 0.01, is_active: true },
    ups: { power_w: 1100, power_kw: 1.10, is_active: true }
  };

  const formatPower = (watts: number, kw: number) => {
    if (watts >= 1000) {
      return `${kw.toFixed(2)} kW`;
    }
    return `${watts.toFixed(2)} W`;
  };

  const pvActive = nodes.solar.power_w > 10;
  const battDischarging = nodes.battery.is_discharging && nodes.battery.power_w > 10;
  const battCharging = nodes.battery.is_charging && nodes.battery.power_w > 10;
  const gridImporting = nodes.grid.is_importing && nodes.grid.power_w > 5;
  const gridExporting = nodes.grid.is_exporting && nodes.grid.power_w > 5;
  const upsActive = nodes.ups.power_w > 10;
  const loadActive = nodes.load.power_w > 5;

  const pathPvToInv = "M 115 75 H 175 V 155 H 205";
  const pathBattToInv = "M 115 265 H 175 V 165 H 205";
  const pathInvToBatt = "M 205 165 H 175 V 265 H 115";
  const pathGridToInv = "M 385 75 H 325 V 155 H 295";
  const pathInvToGrid = "M 295 155 H 325 V 75 H 385";
  const pathInvToUps = "M 250 190 V 235";
  const pathInvToLoad = "M 295 165 H 325 V 265 H 385";

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm h-full flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Flow Graph</h3>
          <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
            {data?.last_update_time ? format12HourTime(data.last_update_time, true) : ''}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <button
              onClick={() => setDataMode(dataMode === 'plant' ? 'live' : 'plant')}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-md transition-colors"
            >
              <span>{dataMode === 'plant' ? 'Plant data' : 'Live Telemetry'}</span>
              <ChevronDown className="h-3 w-3 text-slate-400" />
            </button>
          </div>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-2 py-1 text-xs font-medium rounded-md transition-colors ${
              autoRefresh
                ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
            }`}
          >
            {autoRefresh ? `${secondsUntilRefresh}s` : 'Paused'}
          </button>

          <button
            onClick={() => fetchFlowData()}
            disabled={loading}
            title={autoRefresh ? `Auto-refresh in ${secondsUntilRefresh}s` : 'Manual refresh'}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-solar-500' : ''}`} />
          </button>
        </div>
      </div>

      <div className="relative w-full aspect-[500/320] select-none bg-slate-50/50 dark:bg-slate-950/40 rounded-lg p-2 overflow-hidden border border-slate-100 dark:border-slate-800/60">
        <svg viewBox="0 0 500 320" className="w-full h-full">
          <defs>
            <filter id="glow-solar" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glow-batt" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glow-grid" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glow-load" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          <path d={pathPvToInv} fill="none" stroke="#CBD5E1" strokeWidth="2" strokeDasharray="5 5" className="dark:stroke-slate-700" />
          <path d={pathBattToInv} fill="none" stroke="#CBD5E1" strokeWidth="2" strokeDasharray="5 5" className="dark:stroke-slate-700" />
          <path d={pathGridToInv} fill="none" stroke="#CBD5E1" strokeWidth="2" strokeDasharray="5 5" className="dark:stroke-slate-700" />
          <path d={pathInvToUps} fill="none" stroke="#CBD5E1" strokeWidth="2" strokeDasharray="5 5" className="dark:stroke-slate-700" />
          <path d={pathInvToLoad} fill="none" stroke="#CBD5E1" strokeWidth="2" strokeDasharray="5 5" className="dark:stroke-slate-700" />

          {pvActive && (
            <>
              <path d={pathPvToInv} fill="none" stroke="#F59E0B" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-solar)" />
              <circle r="4" fill="#F59E0B">
                <animateMotion path={pathPvToInv} dur="1.8s" repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#FDE68A">
                <animateMotion path={pathPvToInv} dur="1.8s" begin="0.9s" repeatCount="indefinite" />
              </circle>
            </>
          )}

          {battDischarging && (
            <>
              <path d={pathBattToInv} fill="none" stroke="#10B981" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-batt)" />
              <circle r="4" fill="#10B981">
                <animateMotion path={pathBattToInv} dur="1.8s" repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#6EE7B7">
                <animateMotion path={pathBattToInv} dur="1.8s" begin="0.9s" repeatCount="indefinite" />
              </circle>
            </>
          )}

          {battCharging && (
            <>
              <path d={pathInvToBatt} fill="none" stroke="#3B82F6" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-batt)" />
              <circle r="4" fill="#3B82F6">
                <animateMotion path={pathInvToBatt} dur="1.8s" repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#93C5FD">
                <animateMotion path={pathInvToBatt} dur="1.8s" begin="0.9s" repeatCount="indefinite" />
              </circle>
            </>
          )}

          {gridImporting && (
            <>
              <path d={pathGridToInv} fill="none" stroke="#6366F1" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.5s_linear_infinite]" filter="url(#glow-grid)" />
              <circle r="4" fill="#6366F1">
                <animateMotion path={pathGridToInv} dur="2.2s" repeatCount="indefinite" />
              </circle>
            </>
          )}

          {gridExporting && (
            <>
              <path d={pathInvToGrid} fill="none" stroke="#10B981" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.5s_linear_infinite]" filter="url(#glow-grid)" />
              <circle r="4" fill="#10B981">
                <animateMotion path={pathInvToGrid} dur="2.2s" repeatCount="indefinite" />
              </circle>
            </>
          )}

          {upsActive && (
            <>
              <path d={pathInvToUps} fill="none" stroke="#0EA5E9" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-load)" />
              <circle r="4" fill="#0EA5E9">
                <animateMotion path={pathInvToUps} dur="1.4s" repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#7DD3FC">
                <animateMotion path={pathInvToUps} dur="1.4s" begin="0.7s" repeatCount="indefinite" />
              </circle>
            </>
          )}

          {loadActive && (
            <>
              <path d={pathInvToLoad} fill="none" stroke="#F97316" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.4s_linear_infinite]" filter="url(#glow-load)" />
              <circle r="4" fill="#F97316">
                <animateMotion path={pathInvToLoad} dur="2.0s" repeatCount="indefinite" />
              </circle>
            </>
          )}
        </svg>

        <div className="absolute top-[8%] left-[7%] flex flex-col items-center">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border transition-all ${
            pvActive
              ? 'bg-amber-500/10 border-amber-500/40 text-amber-500 shadow-sm shadow-amber-500/20'
              : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
          }`}>
            <Sun className={`h-6 w-6 ${pvActive ? 'text-amber-500' : 'text-slate-400'}`} />
          </div>
          <span className="mt-1.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
            {formatPower(nodes.solar.power_w, nodes.solar.power_kw)}
          </span>
        </div>

        <div className="absolute top-[8%] right-[7%] flex flex-col items-center">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border transition-all ${
            gridImporting
              ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-500 shadow-sm shadow-indigo-500/20'
              : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
          }`}>
            <Zap className={`h-6 w-6 ${gridImporting ? 'text-indigo-500' : 'text-slate-400'}`} />
          </div>
          <span className="mt-1.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
            {formatPower(nodes.grid.power_w, nodes.grid.power_kw)}
          </span>
          <div className="mt-1 flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-2.5 w-2.5" />
            <span>{nodes.grid.status_label}</span>
          </div>
        </div>

        <div className="absolute top-[37%] left-[41%] flex flex-col items-center">
          <div className="w-20 h-16 rounded-xl bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 shadow-sm flex flex-col items-center justify-center p-1.5">
            <div className="w-6 h-4 rounded-sm border border-slate-400 dark:border-slate-500 bg-slate-100 dark:bg-slate-700 flex items-center justify-center mb-1">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <span className="text-[11px] font-semibold text-slate-800 dark:text-slate-200">Inverter</span>
          </div>
        </div>

        <div className="absolute bottom-[6%] left-[7%] flex flex-col items-center">
          <div className="relative">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border transition-all ${
              battDischarging || battCharging
                ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-500 shadow-sm shadow-emerald-500/20'
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
            }`}>
              <Battery className={`h-6 w-6 ${battDischarging || battCharging ? 'text-emerald-500' : 'text-slate-400'}`} />
            </div>
            <span className="absolute -top-2 -right-2 px-1.5 py-0.5 rounded-md bg-emerald-600 text-white text-[10px] font-bold shadow-sm">
              {nodes.battery.soc_percent.toFixed(0)}%
            </span>
          </div>
          <span className="mt-1.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
            {formatPower(nodes.battery.power_w, nodes.battery.power_kw)}
          </span>
        </div>

        <div className="absolute bottom-[6%] left-[41%] flex flex-col items-center">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border transition-all ${
            upsActive
              ? 'bg-sky-500/10 border-sky-500/40 text-sky-500 shadow-sm shadow-sky-500/20'
              : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
          }`}>
            <ShieldCheck className={`h-6 w-6 ${upsActive ? 'text-sky-500' : 'text-slate-400'}`} />
          </div>
          <span className="mt-1.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
            {formatPower(nodes.ups.power_w, nodes.ups.power_kw)}
          </span>
        </div>

        <div className="absolute bottom-[6%] right-[7%] flex flex-col items-center">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center border transition-all ${
            loadActive
              ? 'bg-orange-500/10 border-orange-500/40 text-orange-500 shadow-sm shadow-orange-500/20'
              : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
          }`}>
            <Home className={`h-6 w-6 ${loadActive ? 'text-orange-500' : 'text-slate-400'}`} />
          </div>
          <span className="mt-1.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
            {formatPower(nodes.load.power_w, nodes.load.power_kw)}
          </span>
        </div>
      </div>
    </div>
  );
};
