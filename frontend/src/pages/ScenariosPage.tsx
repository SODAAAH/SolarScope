import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { Sliders, CheckCircle2, BatteryCharging, Sun, Zap, Clock, ShieldAlert } from 'lucide-react';
import type { ViewMode } from '../lib/terminology';

export const ScenariosPage: React.FC = () => {
  const { activeDatasetId, viewMode } = useOutletContext<{
    activeDatasetId: string;
    viewMode: ViewMode;
  }>();
  const [addBattery, setAddBattery] = useState<number>(5.0);
  const [addPv, setAddPv] = useState<number>(2.0);
  const [reserveSoc, setReserveSoc] = useState<number>(20.0);
  const [shiftLoad, setShiftLoad] = useState<number>(2.0);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runSim = () => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.runScenario(activeDatasetId, {
      add_battery_kwh: addBattery,
      add_pv_kwp: addPv,
      new_reserve_soc: reserveSoc,
      shift_load_kwh: shiftLoad
    })
      .then(setScenarioResult)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (activeDatasetId) {
      runSim();
    }
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset in the scope dropdown.</div>;
  }

  const res = scenarioResult;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            {viewMode === 'simple' ? 'What If? Upgrade & Savings Simulator' : 'Empirical Parametric Scenario Simulation'}
          </h1>
          <p className="text-xs text-slate-500">
            Test how a bigger battery, more solar panels, or shifting appliances into sunny hours would reduce your electricity purchases from TEI.
          </p>
        </div>
      </div>

      <div className="p-3 bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/50 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
        <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
        <p className="leading-relaxed">
          Simulations run on your actual historical electricity usage. They predict what would happen under these test assumptions without changing any physical inverter settings or hardware.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 space-y-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <Sliders className="h-4 w-4 text-solar-600" />
              Adjust What If? Settings
            </h2>
            <span className="text-[10px] font-mono text-slate-400">Simulation</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-700 dark:text-slate-300 font-medium flex items-center gap-1">
                <BatteryCharging className="w-3.5 h-3.5 text-teal-600" />
                Larger Battery Capacity
              </span>
              <span className="font-mono font-bold text-teal-600 dark:text-teal-400">+{addBattery} kWh</span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              step="2.5"
              value={addBattery}
              onChange={(e) => setAddBattery(parseFloat(e.target.value))}
              className="w-full accent-teal-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-0.5">Stores more afternoon solar power for the night.</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-700 dark:text-slate-300 font-medium flex items-center gap-1">
                <Sun className="w-3.5 h-3.5 text-amber-500" />
                Additional Solar Panels
              </span>
              <span className="font-mono font-bold text-amber-600 dark:text-amber-400">+{addPv} kWp</span>
            </div>
            <input
              type="range"
              min="0"
              max="10"
              step="1"
              value={addPv}
              onChange={(e) => setAddPv(parseFloat(e.target.value))}
              className="w-full accent-amber-500 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-0.5">Increases daytime solar electricity generation.</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-700 dark:text-slate-300 font-medium flex items-center gap-1">
                <Zap className="w-3.5 h-3.5 text-slate-500" />
                Minimum Battery Reserve Level
              </span>
              <span className="font-mono font-bold text-slate-800 dark:text-slate-200">{reserveSoc}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="30"
              step="5"
              value={reserveSoc}
              onChange={(e) => setReserveSoc(parseFloat(e.target.value))}
              className="w-full accent-slate-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-0.5">Lower reserve uses more battery; higher reserve preserves backup.</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-700 dark:text-slate-300 font-medium flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-indigo-500" />
                Shift Evening Appliances to Noon
              </span>
              <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">{shiftLoad} kWh</span>
            </div>
            <input
              type="range"
              min="0"
              max="6"
              step="0.5"
              value={shiftLoad}
              onChange={(e) => setShiftLoad(parseFloat(e.target.value))}
              className="w-full accent-indigo-600 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 block mt-0.5">Running laundry & pumps at noon uses free solar power.</span>
          </div>

          <button
            onClick={runSim}
            disabled={loading}
            className="w-full bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 text-white dark:text-slate-900 text-xs font-semibold py-2.5 rounded-xl transition-colors shadow-sm"
          >
            {loading ? 'Simulating What If...' : 'Update Simulation Results'}
          </button>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm">
              <span className="text-xs text-slate-500 block mb-1">Current TEI Purchases</span>
              <div className="text-xl font-bold font-mono tabular-nums text-slate-700 dark:text-slate-300">
                {res?.baseline_grid_kwh?.toFixed(2) ?? '0.00'} <span className="text-xs font-normal">kWh</span>
              </div>
              <span className="text-[10px] text-slate-400 block mt-1">Observed reality</span>
            </div>

            <div className="p-4 bg-white dark:bg-slate-900 border border-teal-200 dark:border-teal-900/60 rounded-xl shadow-sm">
              <span className="text-xs text-slate-500 block mb-1">Expected TEI Purchases</span>
              <div className="text-xl font-bold font-mono tabular-nums text-teal-600 dark:text-teal-400">
                {res?.modeled_grid_kwh?.toFixed(2) ?? '0.00'} <span className="text-xs font-normal">kWh</span>
              </div>
              <span className="text-[10px] font-semibold text-teal-600 dark:text-teal-400 block mt-1">
                -{res?.grid_reduction_percent ?? 0}% less grid electricity
              </span>
            </div>

            <div className="p-4 bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/60 rounded-xl shadow-sm">
              <span className="text-xs text-slate-500 block mb-1">Estimated Annual Savings</span>
              <div className="text-xl font-bold font-mono tabular-nums text-amber-600 dark:text-amber-400">
                ₱{res?.annual_incremental_savings?.toLocaleString() ?? 0}
              </div>
              <span className="text-[10px] text-slate-400 block mt-1">
                ~₱{res?.daily_incremental_savings ?? 0} per day
              </span>
            </div>

            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm">
              <span className="text-xs text-slate-500 block mb-1">Estimated Payback</span>
              <div className="text-xl font-bold font-mono tabular-nums text-slate-900 dark:text-white">
                {res?.upgrade_payback_years ?? 'N/A'} <span className="text-xs font-normal text-slate-500">years</span>
              </div>
              <span className="text-[10px] text-slate-400 block mt-1">
                Capex: ₱{res?.total_upgrade_cost?.toLocaleString() ?? 0}
              </span>
            </div>
          </div>

          <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Plain-Language Simulation Summary
            </h2>
            <div className="space-y-3 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              <div className="flex items-start gap-2.5 p-3 bg-teal-50/50 dark:bg-teal-950/20 rounded-xl border border-teal-100 dark:border-teal-900/40">
                <CheckCircle2 className="h-4 w-4 text-teal-600 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-slate-900 dark:text-slate-100">Battery Capacity Impact:</strong>
                  <span> Adding <strong>+{addBattery} kWh</strong> of storage would eliminate approximately {res?.grid_reduction_kwh ?? 0} kWh of electricity bought from TEI per day by keeping your home on stored solar energy through the late night.</span>
                </div>
              </div>

              <div className="flex items-start gap-2.5 p-3 bg-amber-50/50 dark:bg-amber-950/20 rounded-xl border border-amber-100 dark:border-amber-900/40">
                <CheckCircle2 className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-slate-900 dark:text-slate-100">Load Shifting Impact:</strong>
                  <span> Shifting <strong>{shiftLoad} kWh</strong> of electricity use into midday (e.g., dishwashing, laundry, water heater) takes advantage of direct rooftop sunshine at zero extra cost.</span>
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl text-[11px] text-slate-500 leading-relaxed">
                <strong>Important Notice:</strong> These estimates are calculated using your actual recorded consumption and solar yield. Results depend on future weather conditions, seasonal sunlight, and electricity rates from TEI. They do not constitute guaranteed savings.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
