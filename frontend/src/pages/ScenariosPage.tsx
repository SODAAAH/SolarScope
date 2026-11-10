import React, { useState, useEffect } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Sliders, BatteryCharging, DollarSign } from "lucide-react";
import { api, type UpgradeSimulationResponse } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { theme } from "../lib/theme";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const ScenariosPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get("tab") as "upgrades" | "load_shift" | "finance") || "upgrades";

  const [addBattery, setAddBattery] = useState<number>(5.0);
  const [addPv, setAddPv] = useState<number>(1.24);
  const [reserveSoc, setReserveSoc] = useState<number>(20.0);
  const [shiftLoad, setShiftLoad] = useState<number>(2.0);

  const [simResult, setSimResult] = useState<UpgradeSimulationResponse | null>(null);
  const [financeData, setFinanceData] = useState<any>(null);
  const [tariffType, setTariffType] = useState<"flat" | "tou" | "tiered">("flat");
  const [flatRate, setFlatRate] = useState<number>(11.50);
  const [systemCapex, setSystemCapex] = useState<number>(250000);

  const [loading, setLoading] = useState(false);

  const setTab = (tab: "upgrades" | "load_shift" | "finance") => {
    setSearchParams({ tab });
  };

  const runSimulation = () => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.simulateHardwareUpgrade(activeDatasetId, {
      add_battery_kwh: addBattery,
      add_pv_kwp: addPv,
      new_reserve_soc: reserveSoc,
      shift_load_kwh: shiftLoad
    })
      .then((data) => setSimResult(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const loadFinance = (type = tariffType, rate = flatRate, capex = systemCapex) => {
    if (!activeDatasetId) return;
    api.getFinance(activeDatasetId, type, rate, capex)
      .then((data) => setFinanceData(data))
      .catch(console.error);
  };

  useEffect(() => {
    if (activeDatasetId) {
      runSimulation();
      loadFinance();
    }
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return (
      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <Sliders className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">No Dataset Active</h3>
        <p className="text-sm text-slate-500 mt-1">Select a dataset to simulate hardware upgrades and financial returns.</p>
      </div>
    );
  }

  const currency = financeData?.currency || "PHP";
  const dailyCost = financeData?.daily_cost ?? financeData?.daily_grid_cost ?? 0;
  const baselineCost = financeData?.counterfactual_daily_cost ?? financeData?.hypothetical_full_grid_cost ?? 0;
  const dailySavings = financeData?.daily_savings ?? financeData?.daily_avoided_cost ?? 0;
  const monthlyCost = dailyCost * 30.5;
  const monthlySavings = dailySavings * 30.5;
  const annualSavings = dailySavings * 365.25;

  const discountRate = 0.06;
  const degradation = 0.005;
  const inflation = 0.035;
  const years = Array.from({ length: 11 }, (_, i) => i);
  let cumulativeCashFlow = -systemCapex;
  const cashFlows: number[] = [cumulativeCashFlow];
  let paybackYear: number | null = null;

  for (let y = 1; y <= 10; y++) {
    const degradedSavings = annualSavings * Math.pow(1 - degradation, y - 1);
    const inflatedSavings = degradedSavings * Math.pow(1 + inflation, y - 1);
    const discountedCashFlow = inflatedSavings / Math.pow(1 + discountRate, y);
    cumulativeCashFlow += discountedCashFlow;
    cashFlows.push(cumulativeCashFlow);
    if (paybackYear === null && cumulativeCashFlow >= 0) {
      paybackYear = y;
    }
  }

  const cashFlowOption = {
    tooltip: { trigger: "axis" },
    grid: { left: "4%", right: "4%", top: "8%", bottom: "12%", containLabel: true },
    xAxis: {
      type: "category",
      data: years.map(y => `Yr ${y}`),
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: {
      type: "value",
      name: currency,
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      {
        name: "Discounted Cash Flow",
        type: "line",
        data: cashFlows,
        itemStyle: { color: theme.colors.emerald },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(16, 185, 129, 0.25)" },
              { offset: 1, color: "rgba(16, 185, 129, 0.02)" }
            ]
          }
        },
        smooth: true
      }
    ]
  };

  const limits = simResult?.electrical_limits;
  const modeled = simResult?.modeled_result;
  const comparisons = simResult?.comparison_options || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            What-If Simulator & Hardware Upgrades
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1">
            Simulate Canadian Solar PV additions and MENRED ESS battery expansion under strict inverter and BMS limits.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg text-xs font-medium w-full sm:w-fit max-w-full overflow-x-auto no-scrollbar whitespace-nowrap">
        <button
          onClick={() => setTab("upgrades")}
          className={`shrink-0 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "upgrades"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <BatteryCharging className="w-3.5 h-3.5" />
          <span>Hardware Upgrades</span>
        </button>
        <button
          onClick={() => setTab("load_shift")}
          className={`shrink-0 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "load_shift"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Parametric Simulation</span>
        </button>
        <button
          onClick={() => setTab("finance")}
          className={`shrink-0 px-3 py-1.5 rounded-md transition-colors flex items-center gap-2 ${
            currentTab === "finance"
              ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <DollarSign className="w-3.5 h-3.5" />
          <span>Financial Payback</span>
        </button>
      </div>

      {currentTab === "upgrades" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Inverter & BMS Electrical Constraints Enforced
            </h3>
            <div className="grid grid-cols-1 min-[480px]:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 text-xs">
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500">Inverter AC Continuous</span>
                <div className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-1">
                  {limits?.inverter_rated_continuous_kw || 6.0} kW
                </div>
                <span className="text-[10px] text-slate-400">Peak {limits?.inverter_peak_apparent_va || 6600} VA</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500">Active Battery Current Limit</span>
                <div className="text-sm font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                  {limits?.effective_battery_current_limit_a || 100} A
                </div>
                <span className="text-[10px] text-slate-400">BMS 100A &lt; Inverter 135A</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500">Max Battery Charge Power</span>
                <div className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-1">
                  {limits?.max_battery_charge_power_kw || 5.12} kW
                </div>
                <span className="text-[10px] text-slate-400">Enforced by 51.2V nominal</span>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-slate-500">MPPT Operating Range</span>
                <div className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-1">
                  {limits?.pv_mppt_operating_range_v || "150 - 425 V"}
                </div>
                <span className="text-[10px] text-slate-400">Max Open Circuit: {limits?.pv_max_voltage_v || "500 V"}</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Hardware Expansion Comparison Scenarios
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Evaluated against historical household load profiles with physical electrical limits.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/50 uppercase tracking-wider text-slate-500 font-semibold border-b border-slate-200 dark:border-slate-800 whitespace-nowrap">
                  <tr>
                    <th className="px-4 py-3">Configuration Option</th>
                    <th className="px-4 py-3">Added Storage / PV</th>
                    <th className="px-4 py-3">Estimated CAPEX</th>
                    <th className="px-4 py-3">Daily Grid Saved</th>
                    <th className="px-4 py-3">Monthly Savings</th>
                    <th className="px-4 py-3">Simple Payback</th>
                    <th className="px-4 py-3">10-Year NPV</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {comparisons.map((opt, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                      <td className="px-4 py-3 font-semibold text-slate-900 dark:text-slate-100">
                        {opt.name}
                        <div className="text-[10px] font-normal text-slate-500">{opt.description}</div>
                      </td>
                      <td className="px-4 py-3 font-mono whitespace-nowrap">
                        {opt.added_battery_kwh > 0 && `+${opt.added_battery_kwh} kWh`}
                        {opt.added_battery_kwh > 0 && opt.added_pv_kwp > 0 && " | "}
                        {opt.added_pv_kwp > 0 && `+${opt.added_pv_kwp} kWp`}
                      </td>
                      <td className="px-4 py-3 font-mono whitespace-nowrap">PHP {opt.estimated_cost_php.toLocaleString()}</td>
                      <td className="px-4 py-3 font-mono whitespace-nowrap text-emerald-600 dark:text-emerald-400 font-semibold">
                        -{opt.daily_grid_reduction_kwh.toFixed(1)} kWh/day
                      </td>
                      <td className="px-4 py-3 font-mono whitespace-nowrap font-bold text-slate-900 dark:text-slate-100">
                        PHP {opt.monthly_savings_php.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td className="px-4 py-3 font-mono whitespace-nowrap">{opt.payback_years.toFixed(1)} yrs</td>
                      <td className="px-4 py-3 font-mono whitespace-nowrap text-emerald-600 dark:text-emerald-400 font-bold">
                        PHP {opt.ten_year_npv_php.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {currentTab === "load_shift" && (
        <div className="bg-white dark:bg-slate-900 p-4 sm:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
            Interactive Parametric Upgrade Controls
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="flex flex-wrap justify-between gap-1 text-xs">
                <span className="font-medium text-slate-700 dark:text-slate-300">Additional Battery Storage</span>
                <span className="font-bold text-amber-600 dark:text-amber-400">{addBattery.toFixed(1)} kWh</span>
              </div>
              <input
                type="range"
                min="0"
                max="32"
                step="2.5"
                value={addBattery}
                onChange={(e) => setAddBattery(parseFloat(e.target.value))}
                className="w-full accent-amber-600"
              />
            </div>

            <div className="space-y-2">
              <div className="flex flex-wrap justify-between gap-1 text-xs">
                <span className="font-medium text-slate-700 dark:text-slate-300">Additional Canadian Solar Panels</span>
                <span className="font-bold text-amber-600 dark:text-amber-400">{addPv.toFixed(2)} kWp ({Math.round(addPv / 0.62)} panels)</span>
              </div>
              <input
                type="range"
                min="0"
                max="6.2"
                step="0.62"
                value={addPv}
                onChange={(e) => setAddPv(parseFloat(e.target.value))}
                className="w-full accent-amber-600"
              />
            </div>

            <div className="space-y-2">
              <div className="flex flex-wrap justify-between gap-1 text-xs">
                <span className="font-medium text-slate-700 dark:text-slate-300">Minimum Battery Reserve State</span>
                <span className="font-bold text-amber-600 dark:text-amber-400">{reserveSoc}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="50"
                step="5"
                value={reserveSoc}
                onChange={(e) => setReserveSoc(parseFloat(e.target.value))}
                className="w-full accent-amber-600"
              />
            </div>

            <div className="space-y-2">
              <div className="flex flex-wrap justify-between gap-1 text-xs">
                <span className="font-medium text-slate-700 dark:text-slate-300">Load Shifted into Peak Solar Hours</span>
                <span className="font-bold text-amber-600 dark:text-amber-400">{shiftLoad.toFixed(1)} kWh/day</span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={shiftLoad}
                onChange={(e) => setShiftLoad(parseFloat(e.target.value))}
                className="w-full accent-amber-600"
              />
            </div>
          </div>

          <div className="pt-2">
            <button
              onClick={runSimulation}
              disabled={loading}
              className="w-full sm:w-auto px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg transition-colors"
            >
              {loading ? "Simulating..." : "Recalculate Simulation"}
            </button>
          </div>

          {modeled && (
            <div className="grid grid-cols-1 min-[480px]:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 pt-4 border-t border-slate-100 dark:border-slate-800">
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-xs text-slate-500">Modeled Daily Grid Import</span>
                <div className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1 tabular-nums">
                  {modeled.modeled_daily_grid_kwh.toFixed(2)} kWh
                </div>
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                  -{modeled.grid_reduction_percentage.toFixed(0)}% grid reduction
                </span>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-xs text-slate-500">Added Night Autonomy</span>
                <div className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1">
                  +{modeled.added_night_autonomy_formatted}
                </div>
                <span className="text-[11px] text-slate-500">Beyond current reserve</span>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-xs text-slate-500">Monthly Avoided Cost</span>
                <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                  PHP {modeled.monthly_savings_php.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
                <span className="text-[11px] text-slate-500">PHP {modeled.annual_savings_php.toLocaleString(undefined, { maximumFractionDigits: 0 })}/yr</span>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="text-xs text-slate-500">Investment Payback</span>
                <div className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1">
                  {modeled.simple_payback_years.toFixed(1)} Years
                </div>
                <span className="text-[11px] text-slate-500">10-Yr NPV: PHP {modeled.ten_year_npv_php.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {currentTab === "finance" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Tariff & CAPEX Settings
            </h3>
            <div className="grid grid-cols-1 min-[480px]:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 items-end">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Tariff Structure</label>
                <select
                  value={tariffType}
                  onChange={(e) => setTariffType(e.target.value as any)}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                >
                  <option value="flat">Single Flat Rate</option>
                  <option value="tou">Time of Use (TOU)</option>
                  <option value="tiered">Tiered Stepped Rate</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Flat Rate ({currency}/kWh)</label>
                <input
                  type="number"
                  step="0.1"
                  value={flatRate}
                  onChange={(e) => setFlatRate(Number(e.target.value))}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Initial System CAPEX ({currency})</label>
                <input
                  type="number"
                  step="5000"
                  value={systemCapex}
                  onChange={(e) => setSystemCapex(Number(e.target.value))}
                  className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                />
              </div>

              <div>
                <button
                  onClick={() => loadFinance(tariffType, flatRate, systemCapex)}
                  className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs rounded-lg transition-colors"
                >
                  Apply Tariff
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 min-[480px]:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Observed Daily Cost</span>
              <div className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1 tabular-nums">
                {currency} {dailyCost.toFixed(2)}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">~{currency} {monthlyCost.toFixed(0)} / month projected</p>
            </div>
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Baseline Without Solar</span>
              <div className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1 tabular-nums">
                {currency} {baselineCost.toFixed(2)}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">100% grid supply counterfactual</p>
            </div>
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monthly Avoided Cost</span>
              <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1 tabular-nums">
                {currency} {monthlySavings.toFixed(0)}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">Combined PV + Battery offset</p>
            </div>
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">10-Year Discounted NPV</span>
              <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1 tabular-nums">
                {currency} {cashFlows[10]?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">6% discount, 3.5% inflation</p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-4 sm:p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                10-Year Discounted Cash Flow NPV & System Payback
              </h3>
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                Payback: {paybackYear ? `${paybackYear} Years` : "> 10 Years"}
              </span>
            </div>
            <EChartComponent option={cashFlowOption} height="290px" />
          </div>
        </div>
      )}
    </div>
  );
};
