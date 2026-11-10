import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Sun, Zap, Battery, Home, ShieldCheck, RefreshCw, CheckCircle2, WifiOff } from 'lucide-react';
import type { LiveFlowResponse } from '../../lib/api';
import { api } from '../../lib/api';
import { format12HourTime } from '../../lib/formatters';
import { Tooltip } from '../common/Tooltip';

interface LiveFlowGraphProps {
  initialData?: LiveFlowResponse | null;
  onFlowUpdate?: (flow: LiveFlowResponse) => void;
  onRefreshRequested?: () => void;
}

const LIVE_FLOW_CACHE_KEY = 'solarscope_cached_live_flow_v2';
const REFRESH_INTERVAL_SEC = 15;

const NEUTRAL_NODES: LiveFlowResponse['nodes'] = {
  solar: { power_w: 0.0, power_kw: 0.0, is_active: false },
  battery: { soc_percent: 0, power_w: 0.0, power_kw: 0.0, state: 'IDLE', is_charging: false, is_discharging: false },
  inverter: { status: 'STANDBY', throughput_w: 0.0, throughput_kw: 0.0 },
  grid: { power_w: 0.0, power_kw: 0.0, status_label: 'Standby', state: 'IDLE', is_importing: false, is_exporting: false },
  load: { power_w: 0.0, power_kw: 0.0, is_active: false },
  ups: { power_w: 0.0, power_kw: 0.0, is_active: false }
};

export const LiveFlowGraph: React.FC<LiveFlowGraphProps> = ({
  initialData,
  onFlowUpdate,
  onRefreshRequested
}) => {
  const [data, setData] = useState<LiveFlowResponse | null>(() => {
    if (initialData && (initialData.is_live || initialData.data_source === 'demo')) {
      return initialData;
    }
    try {
      const saved = localStorage.getItem(LIVE_FLOW_CACHE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as LiveFlowResponse;
        if (parsed && (parsed.is_live || parsed.data_source === 'demo')) {
          return parsed;
        }
      }
    } catch {}
    return null;
  });
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(REFRESH_INTERVAL_SEC);

  const isFetchingRef = useRef(false);
  const onFlowUpdateRef = useRef(onFlowUpdate);
  const onRefreshRequestedRef = useRef(onRefreshRequested);

  useEffect(() => {
    onFlowUpdateRef.current = onFlowUpdate;
  }, [onFlowUpdate]);

  useEffect(() => {
    onRefreshRequestedRef.current = onRefreshRequested;
  }, [onRefreshRequested]);

  const fetchFlowData = useCallback(async (triggerSummaryRefresh = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setLoading(true);
    try {
      const res = await api.getDeyeLiveFlow();
      if (res) {
        const hasRealData = Boolean(
          res.is_live || res.data_source === 'demo' || res.data_source === 'cached'
        );
        if (hasRealData) {
          setData(res);
          try {
            if (res.is_live || res.data_source === 'demo') {
              localStorage.setItem(LIVE_FLOW_CACHE_KEY, JSON.stringify(res));
            }
          } catch {}
          if (onFlowUpdateRef.current) {
            onFlowUpdateRef.current(res);
          }
        } else {
          setData((prev) => {
            if (prev && (prev.is_live || prev.data_source === 'cached')) {
              return {
                ...prev,
                is_live: false,
                data_source: 'cached',
                error: res.error || 'Live telemetry temporarily unreachable'
              };
            }
            return res;
          });
          if (onFlowUpdateRef.current) {
            onFlowUpdateRef.current(res);
          }
        }
      }
    } catch {
    } finally {
      isFetchingRef.current = false;
      setLoading(false);
      setSecondsUntilRefresh(REFRESH_INTERVAL_SEC);
      if (triggerSummaryRefresh && onRefreshRequestedRef.current) {
        onRefreshRequestedRef.current();
      }
    }
  }, []);

  useEffect(() => {
    if (initialData && (initialData.is_live || initialData.data_source === 'demo')) {
      setData(initialData);
    }
  }, [initialData]);

  useEffect(() => {
    fetchFlowData(false);
  }, [fetchFlowData]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      setSecondsUntilRefresh((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  useEffect(() => {
    if (autoRefresh && secondsUntilRefresh === 0) {
      fetchFlowData(false);
    }
  }, [autoRefresh, secondsUntilRefresh, fetchFlowData]);

  const nodes = data?.nodes || NEUTRAL_NODES;
  const sourceState = data?.data_source || (data?.is_live ? 'live' : 'offline');

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

  const pathPvToInv = "M 103 60 H 155 V 120 H 208";
  const pathBattToInv = "M 103 220 H 155 V 150 H 208";
  const pathInvToBatt = "M 208 150 H 155 V 220 H 103";
  const pathGridToInv = "M 397 60 H 345 V 120 H 292";
  const pathInvToGrid = "M 292 120 H 345 V 60 H 397";
  const pathInvToUps = "M 250 167 V 197";
  const pathInvToLoad = "M 292 150 H 345 V 220 H 397";

  const getSpeed = (watts: number) => {
    const w = Math.abs(watts);
    if (w > 3000) return { dur: "0.9s", half: "0.45s" };
    if (w > 1500) return { dur: "1.3s", half: "0.65s" };
    if (w > 500) return { dur: "1.8s", half: "0.9s" };
    return { dur: "2.4s", half: "1.2s" };
  };

  const pvSpeed = getSpeed(nodes.solar.power_w);
  const battSpeed = getSpeed(nodes.battery.power_w);
  const gridSpeed = getSpeed(nodes.grid.power_w);
  const upsSpeed = getSpeed(nodes.ups.power_w);
  const loadSpeed = getSpeed(nodes.load.power_w);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-sm h-full flex flex-col justify-between interactive-card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 sm:mb-4">
        <div className="flex items-center gap-2 min-w-0">
          <Tooltip
            title="Live Energy Flow"
            content="Real-time physical power vectors showing current generation, battery charge/discharge, grid import/export, and home consumption."
            position="bottom"
          >
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 cursor-help">Flow Graph</h3>
          </Tooltip>
          {data?.last_update_time && (
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded shrink-0">
              {format12HourTime(data.last_update_time, true)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2">
          {sourceState === 'live' && (
            <Tooltip
              title="Deye Cloud Synchronized"
              content="Connected directly to Deye OpenAPI station telemetry."
              position="bottom"
            >
              <span className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-[11px] font-medium rounded-md bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live
              </span>
            </Tooltip>
          )}

          {sourceState === 'demo' && (
            <Tooltip
              title="Simulated Demo Stream"
              content="Running in Demo Mode. Configure your Deye Cloud credentials in Data Library & Cloud for real station telemetry."
              position="bottom"
            >
              <Link
                to="/library?tab=cloud"
                className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-[11px] font-medium rounded-md bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                Demo
              </Link>
            </Tooltip>
          )}

          {sourceState === 'cached' && (
            <Tooltip
              title="Showing Cached Snapshot"
              content={data?.error || 'Live telemetry temporarily unreachable; retaining your last verified reading until next refresh.'}
              position="bottom"
            >
              <span className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-[11px] font-medium rounded-md bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 cursor-help">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                Cached
              </span>
            </Tooltip>
          )}

          {sourceState === 'offline' && (
            <Tooltip
              title="Live Telemetry Offline"
              content={data?.error || 'Open Data Library & Cloud and click Test API Connection to stream live Deye telemetry.'}
              position="bottom"
            >
              <Link
                to="/library?tab=cloud"
                className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 text-[11px] font-medium rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              >
                <WifiOff className="h-3 w-3 text-slate-400" />
                <span>Offline</span>
              </Link>
            </Tooltip>
          )}

          <Tooltip
            title="Auto Refresh Rate"
            content={autoRefresh ? `Telemetry polls live registers every ${REFRESH_INTERVAL_SEC} seconds. Next refresh in ${secondsUntilRefresh}s.` : 'Polling paused. Click to resume auto-refresh.'}
            position="bottom"
          >
            <button
              type="button"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-2 py-1 text-xs font-medium rounded-md transition-colors ${
                autoRefresh
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
              }`}
            >
              {autoRefresh ? `${secondsUntilRefresh}s` : 'Paused'}
            </button>
          </Tooltip>

          <button
            type="button"
            onClick={() => fetchFlowData(true)}
            disabled={loading}
            title={autoRefresh ? `Auto-refresh in ${secondsUntilRefresh}s` : 'Manual refresh'}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-solar-500' : ''}`} />
          </button>
        </div>
      </div>

      <div className="relative w-full aspect-[500/320] min-h-[210px] select-none bg-slate-50/50 dark:bg-slate-950/40 rounded-lg border border-slate-100 dark:border-slate-800/60 overflow-visible">
        <svg viewBox="0 0 500 320" className="w-full h-full pointer-events-none">
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
                <animateMotion path={pathPvToInv} dur={pvSpeed.dur} repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#FCD34D">
                <animateMotion path={pathPvToInv} dur={pvSpeed.dur} begin={pvSpeed.half} repeatCount="indefinite" />
              </circle>
            </>
          )}

          {battDischarging && (
            <>
              <path d={pathBattToInv} fill="none" stroke="#10B981" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-batt)" />
              <circle r="4" fill="#10B981">
                <animateMotion path={pathBattToInv} dur={battSpeed.dur} repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#6EE7B7">
                <animateMotion path={pathBattToInv} dur={battSpeed.dur} begin={battSpeed.half} repeatCount="indefinite" />
              </circle>
            </>
          )}

          {battCharging && (
            <>
              <path d={pathInvToBatt} fill="none" stroke="#3B82F6" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-batt)" />
              <circle r="4" fill="#3B82F6">
                <animateMotion path={pathInvToBatt} dur={battSpeed.dur} repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#93C5FD">
                <animateMotion path={pathInvToBatt} dur={battSpeed.dur} begin={battSpeed.half} repeatCount="indefinite" />
              </circle>
            </>
          )}

          {gridImporting && (
            <>
              <path d={pathGridToInv} fill="none" stroke="#6366F1" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.5s_linear_infinite]" filter="url(#glow-grid)" />
              <circle r="4" fill="#6366F1">
                <animateMotion path={pathGridToInv} dur={gridSpeed.dur} repeatCount="indefinite" />
              </circle>
            </>
          )}

          {gridExporting && (
            <>
              <path d={pathInvToGrid} fill="none" stroke="#10B981" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.5s_linear_infinite]" filter="url(#glow-grid)" />
              <circle r="4" fill="#10B981">
                <animateMotion path={pathInvToGrid} dur={gridSpeed.dur} repeatCount="indefinite" />
              </circle>
            </>
          )}

          {upsActive && (
            <>
              <path d={pathInvToUps} fill="none" stroke="#0EA5E9" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.2s_linear_infinite]" filter="url(#glow-load)" />
              <circle r="4" fill="#0EA5E9">
                <animateMotion path={pathInvToUps} dur={upsSpeed.dur} repeatCount="indefinite" />
              </circle>
              <circle r="3" fill="#7DD3FC">
                <animateMotion path={pathInvToUps} dur={upsSpeed.dur} begin={upsSpeed.half} repeatCount="indefinite" />
              </circle>
            </>
          )}

          {loadActive && (
            <>
              <path d={pathInvToLoad} fill="none" stroke="#F97316" strokeWidth="2.5" strokeDasharray="6 6" className="animate-[dash_1.4s_linear_infinite]" filter="url(#glow-load)" />
              <circle r="4" fill="#F97316">
                <animateMotion path={pathInvToLoad} dur={loadSpeed.dur} repeatCount="indefinite" />
              </circle>
            </>
          )}
        </svg>

        <div className="absolute inset-0 pointer-events-none">
          <div style={{ left: '15%', top: '18.75%' }} className="absolute -translate-x-1/2 -mt-5 min-[400px]:-mt-6 sm:-mt-7 pointer-events-auto">
            <Tooltip
              title="Rooftop Solar PV Array"
              content="Real-time direct-current (DC) power generated by your photovoltaic rooftop panels right now."
              provenance="Measured"
              position="bottom"
            >
              <div className="flex flex-col items-center cursor-help">
                <div className={`w-10 h-10 min-[400px]:w-12 min-[400px]:h-12 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl flex items-center justify-center border transition-all ${
                  pvActive
                    ? 'bg-amber-500/10 border-amber-500/40 text-amber-500 shadow-sm shadow-amber-500/20'
                    : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
                }`}>
                  <Sun className={`h-4 w-4 sm:h-6 sm:w-6 ${pvActive ? 'text-amber-500' : 'text-slate-400'}`} />
                </div>
                <span className="mt-1 text-[10px] sm:text-xs font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                  {formatPower(nodes.solar.power_w, nodes.solar.power_kw)}
                </span>
              </div>
            </Tooltip>
          </div>

          <div style={{ left: '85%', top: '18.75%' }} className="absolute -translate-x-1/2 -mt-5 min-[400px]:-mt-6 sm:-mt-7 pointer-events-auto">
            <Tooltip
              title="Utility Grid Connection (TEI)"
              content="Current power exchange with the TEI electric grid. Positive watts indicate importing power; negative watts indicate exporting surplus solar."
              provenance="Measured"
              position="bottom"
            >
              <div className="flex flex-col items-center cursor-help">
                <div className={`w-10 h-10 min-[400px]:w-12 min-[400px]:h-12 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl flex items-center justify-center border transition-all ${
                  gridImporting
                    ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-500 shadow-sm shadow-indigo-500/20'
                    : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
                }`}>
                  <Zap className={`h-4 w-4 sm:h-6 sm:w-6 ${gridImporting ? 'text-indigo-500' : 'text-slate-400'}`} />
                </div>
                <span className="mt-1 text-[10px] sm:text-xs font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                  {formatPower(nodes.grid.power_w, nodes.grid.power_kw)}
                </span>
                <div className={`mt-0.5 sm:mt-1 flex items-center gap-0.5 sm:gap-1 px-1.5 py-0.5 rounded-full border text-[9px] sm:text-[10px] font-medium whitespace-nowrap ${
                  nodes.grid.status_label === 'On grid'
                    ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400'
                    : nodes.grid.status_label === 'Off grid'
                      ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-600 dark:text-amber-400'
                      : 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400'
                }`}>
                  <CheckCircle2 className="h-2.5 w-2.5 shrink-0" />
                  <span>{nodes.grid.status_label}</span>
                </div>
              </div>
            </Tooltip>
          </div>

          <div style={{ left: '50%', top: '42.2%' }} className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto">
            <Tooltip
              title="Hybrid Inverter"
              content="Central bi-directional inverter managing power conversion between solar DC, battery storage, and 230V AC home appliances."
              provenance="Measured"
              position="top"
            >
              <div className="w-[68px] h-[44px] min-[400px]:w-[78px] min-[400px]:h-[54px] sm:w-[86px] sm:h-[64px] rounded-xl bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 shadow-sm flex flex-col items-center justify-center p-1 sm:p-1.5 cursor-help">
                <div className="w-5 h-3.5 sm:w-6 sm:h-4 rounded-sm border border-slate-400 dark:border-slate-500 bg-slate-100 dark:bg-slate-700 flex items-center justify-center mb-0.5 sm:mb-1">
                  <div className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${
                    sourceState === 'live'
                      ? 'bg-emerald-500 animate-pulse'
                      : sourceState === 'demo' || sourceState === 'cached'
                        ? 'bg-amber-500 animate-pulse'
                        : 'bg-slate-400'
                  }`} />
                </div>
                <span className="text-[10px] sm:text-[11px] font-semibold text-slate-800 dark:text-slate-200">Inverter</span>
              </div>
            </Tooltip>
          </div>

          <div style={{ left: '15%', top: '68.75%' }} className="absolute -translate-x-1/2 -mt-5 min-[400px]:-mt-6 sm:-mt-7 pointer-events-auto">
            <Tooltip
              title="Battery Storage (LiFePO4)"
              content="State of Charge (SOC) and real-time charging or discharging rate of your lithium iron phosphate home battery system."
              formula="SOC(t) = Q_rem(t) / Q_nominal × 100%"
              provenance="Measured"
              position="top"
            >
              <div className="flex flex-col items-center cursor-help">
                <div className="relative">
                  <div className={`w-10 h-10 min-[400px]:w-12 min-[400px]:h-12 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl flex items-center justify-center border transition-all ${
                    battDischarging || battCharging
                      ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-500 shadow-sm shadow-emerald-500/20'
                      : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
                  }`}>
                    <Battery className={`h-4 w-4 sm:h-6 sm:w-6 ${battDischarging || battCharging ? 'text-emerald-500' : 'text-slate-400'}`} />
                  </div>
                  <span className="absolute -top-2 -right-2 px-1 sm:px-1.5 py-0.5 rounded-md bg-emerald-600 text-white text-[9px] sm:text-[10px] font-bold shadow-sm">
                    {nodes.battery.soc_percent.toFixed(0)}%
                  </span>
                </div>
                <span className="mt-1 text-[10px] sm:text-xs font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                  {formatPower(nodes.battery.power_w, nodes.battery.power_kw)}
                </span>
              </div>
            </Tooltip>
          </div>

          <div style={{ left: '50%', top: '61.5%' }} className="absolute -translate-x-1/2 pointer-events-auto">
            <Tooltip
              title="Critical UPS Backup Port"
              content="Protected household circuits connected to the inverter dedicated emergency EPS backup port, running seamlessly without grid outages."
              provenance="Measured"
              position="top"
            >
              <div className="flex flex-col items-center cursor-help">
                <div className={`w-10 h-10 min-[400px]:w-12 min-[400px]:h-12 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl flex items-center justify-center border transition-all ${
                  upsActive
                    ? 'bg-sky-500/10 border-sky-500/40 text-sky-500 shadow-sm shadow-sky-500/20'
                    : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
                }`}>
                  <ShieldCheck className={`h-4 w-4 sm:h-6 sm:w-6 ${upsActive ? 'text-sky-500' : 'text-slate-400'}`} />
                </div>
                <span className="mt-1 text-[10px] sm:text-xs font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                  {formatPower(nodes.ups.power_w, nodes.ups.power_kw)}
                </span>
              </div>
            </Tooltip>
          </div>

          <div style={{ left: '85%', top: '68.75%' }} className="absolute -translate-x-1/2 -mt-5 min-[400px]:-mt-6 sm:-mt-7 pointer-events-auto">
            <Tooltip
              title="Household Consumption"
              content="Total instantaneous power consumed across all circuits, appliances, air conditioners, and devices in your home."
              provenance="Measured"
              position="top"
            >
              <div className="flex flex-col items-center cursor-help">
                <div className={`w-10 h-10 min-[400px]:w-12 min-[400px]:h-12 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl flex items-center justify-center border transition-all ${
                  loadActive
                    ? 'bg-orange-500/10 border-orange-500/40 text-orange-500 shadow-sm shadow-orange-500/20'
                    : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400'
                }`}>
                  <Home className={`h-4 w-4 sm:h-6 sm:w-6 ${loadActive ? 'text-orange-500' : 'text-slate-400'}`} />
                </div>
                <span className="mt-1 text-[10px] sm:text-xs font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                  {formatPower(nodes.load.power_w, nodes.load.power_kw)}
                </span>
              </div>
            </Tooltip>
          </div>
        </div>
      </div>
    </div>
  );
};
