import React, { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { DollarSign, PiggyBank, Receipt, ArrowUpRight, Percent } from "lucide-react";
import { api } from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { theme } from "../lib/theme";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const FinancePage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [loading, setLoading] = useState(false);
  const [tariffType, setTariffType] = useState<"flat" | "tou" | "tiered">("flat");
  const [flatRate, setFlatRate] = useState<number>(11.50);
  const [systemCapex, setSystemCapex] = useState<number>(250000);
  const [financeData, setFinanceData] = useState<any>(null);

  const loadFinance = async (type = tariffType, rate = flatRate) => {
    if (!activeDatasetId) return;
    setLoading(true);
    try {
      const data = await api.getFinance(activeDatasetId, type, rate);
      setFinanceData(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFinance();
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return (
      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <DollarSign className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">No Dataset Active</h3>
        <p className="text-sm text-slate-500 mt-1">Select or import a dataset to analyze electricity tariffs and investment returns.</p>
      </div>
    );
  }

  const currency = financeData?.currency || "PHP";
  const dailyCost = financeData?.daily_cost || 0;
  const baselineCost = financeData?.counterfactual_daily_cost || 0;
  const dailySavings = financeData?.daily_savings || 0;
  const savingsPct = baselineCost > 0 ? (dailySavings / baselineCost) * 100 : 0;
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
    const adjustedSavings = annualSavings * Math.pow(1 - degradation, y - 1) * Math.pow(1 + inflation, y - 1);
    const discountedValue = adjustedSavings / Math.pow(1 + discountRate, y);
    cumulativeCashFlow += discountedValue;
    cashFlows.push(cumulativeCashFlow);
    if (paybackYear === null && cumulativeCashFlow >= 0) {
      paybackYear = y;
    }
  }

  const npv10 = cumulativeCashFlow;

  const cashFlowOption = {
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        const val = params[0].value;
        const yr = params[0].name;
        return `Year ${yr}: ${currency} ${Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }
    },
    grid: { left: "4%", right: "4%", top: "10%", bottom: "12%", containLabel: true },
    xAxis: {
      type: "category",
      data: years.map(y => `Yr ${y}`),
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: {
      type: "value",
      name: `${currency}`,
      axisLine: { lineStyle: { color: "#94a3b8" } },
      splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
    },
    series: [
      {
        name: "Cumulative Net Cash Flow",
        type: "line",
        data: cashFlows,
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: theme.colors.emerald },
        lineStyle: { width: 3, color: theme.colors.emerald },
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(16, 185, 129, 0.25)" },
              { offset: 1, color: "rgba(16, 185, 129, 0.0)" }
            ]
          }
        },
        markLine: {
          silent: true,
          data: [{ yAxis: 0, lineStyle: { color: "#dc2626", type: "solid", width: 1.5 } }]
        }
      }
    ]
  };

  const costComparisonOption = {
    tooltip: { trigger: "axis" },
    grid: { left: "4%", right: "4%", top: "10%", bottom: "10%", containLabel: true },
    xAxis: {
      type: "category",
      data: ["Daily Actual", "Daily Baseline", "Monthly Actual", "Monthly Baseline"],
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
        name: "Utility Cost",
        type: "bar",
        barWidth: "40%",
        data: [
          { value: dailyCost, itemStyle: { color: theme.colors.teal } },
          { value: baselineCost, itemStyle: { color: theme.colors.coral } },
          { value: monthlyCost, itemStyle: { color: theme.colors.teal } },
          { value: monthlyCost + monthlySavings, itemStyle: { color: theme.colors.coral } }
        ]
      }
    ]
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Financial Modeling & Tariff Analysis
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Deterministic energy cost accounting, counterfactual bill reduction, and 10-year discounted cash flow performance.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
          Tariff Configuration
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Tariff Structure
            </label>
            <select
              value={tariffType}
              onChange={(e) => setTariffType(e.target.value as any)}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="flat">Single Flat Rate</option>
              <option value="tou">Time of Use (TOU)</option>
              <option value="tiered">Tiered Stepped Rate</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              {tariffType === "flat" ? `Flat Rate (${currency}/kWh)` : `Standard Rate (${currency}/kWh)`}
            </label>
            <input
              type="number"
              step="0.1"
              value={flatRate}
              onChange={(e) => setFlatRate(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Initial System CAPEX ({currency})
            </label>
            <input
              type="number"
              step="5000"
              value={systemCapex}
              onChange={(e) => setSystemCapex(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <button
              onClick={() => loadFinance(tariffType, flatRate)}
              disabled={loading}
              className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <DollarSign className="w-4 h-4" />
              {loading ? "Calculating..." : "Apply Tariff"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Observed Daily Cost</span>
            <Receipt className="w-4 h-4 text-slate-500" />
          </div>
          <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {currency} {dailyCost.toFixed(2)}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            ~{currency} {monthlyCost.toFixed(0)} / month projected
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Baseline Without Solar</span>
            <ArrowUpRight className="w-4 h-4 text-orange-500" />
          </div>
          <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
            {currency} {baselineCost.toFixed(2)}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            100% grid supply counterfactual
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Daily Avoided Cost</span>
            <PiggyBank className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
            {currency} {dailySavings.toFixed(2)}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            ~{currency} {monthlySavings.toFixed(0)} / month avoided
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Bill Reduction</span>
            <Percent className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400">
            {savingsPct.toFixed(1)}%
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Effective energy cost offset
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                10-Year Discounted Cash Flow NPV
              </h2>
              <p className="text-xs text-slate-500">
                6.0% discount rate, 0.5% PV degradation, 3.5% tariff inflation
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs font-medium text-slate-500">Payback Period</span>
              <div className="text-sm font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                {paybackYear ? `${paybackYear} Years` : "> 10 Years"}
              </div>
            </div>
          </div>
          <EChartComponent option={cashFlowOption} height="320px" />
          <div className="mt-3 flex justify-between text-xs text-slate-500 px-2">
            <span>10-Yr Net Present Value (NPV):</span>
            <span className="font-semibold tabular-nums text-slate-800 dark:text-slate-200">
              {currency} {npv10.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                Cost Comparison: Actual vs Counterfactual
              </h2>
              <p className="text-xs text-slate-500">
                Energy billing with SolarScope hybrid system vs pure grid reliance
              </p>
            </div>
          </div>
          <EChartComponent option={costComparisonOption} height="320px" />
          <div className="mt-3 grid grid-cols-2 gap-4 text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg">
            <div>
              <span className="font-medium text-slate-800 dark:text-slate-200">Observed Daily Import:</span>
              <span className="ml-1 tabular-nums font-semibold">12.38 kWh</span>
            </div>
            <div>
              <span className="font-medium text-slate-800 dark:text-slate-200">Baseline Demand:</span>
              <span className="ml-1 tabular-nums font-semibold">33.51 kWh</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
