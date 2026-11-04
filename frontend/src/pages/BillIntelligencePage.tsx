import React, { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import {
  ReceiptText,
  Calendar,
  TrendingUp,
  RefreshCw,
  Sliders,
  CheckCircle2,
  Trash2,
  Plus,
  Settings,
  ChevronDown,
  ChevronUp,
  Sun,
  BatteryCharging,
  Info,
  Layers
} from "lucide-react";
import {
  api,
  type BillForecastResponse,
  type BillingProgressResponse,
  type StatementOfAccount,
  type TEIBillingProfile,
  type RateScheduleHistoryItem,
  type HistoricalBillRecord,
  type RateSensitivityResponse
} from "../lib/api";
import { EChartComponent } from "../components/charts/EChartComponent";
import { theme } from "../lib/theme";
import type { ViewMode } from "../lib/terminology";
import { formatDateMMDDYYYY } from "../lib/formatters";

interface OutletContextType {
  activeDatasetId: string | null;
  viewMode: ViewMode;
}

export const BillIntelligencePage: React.FC = () => {
  const { activeDatasetId, viewMode } = useOutletContext<OutletContextType>();

  const [forecast, setForecast] = useState<BillForecastResponse | null>(null);
  const [progressData, setProgressData] = useState<BillingProgressResponse | null>(null);
  const [rates, setRates] = useState<RateScheduleHistoryItem[]>([]);
  const [historyBills, setHistoryBills] = useState<HistoricalBillRecord[]>([]);

  const [statementMode, setStatementMode] = useState<"expected" | "actual" | "lower" | "higher">("expected");
  const [activeTab, setActiveTab] = useState<"statement" | "savings" | "sensitivity" | "history" | "rates">("statement");

  const [loading, setLoading] = useState(true);
  const [checkingRates, setCheckingRates] = useState(false);
  const [checkMessage, setCheckMessage] = useState<string | null>(null);

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAddBillOpen, setIsAddBillOpen] = useState(false);
  const [isManualRateOpen, setIsManualRateOpen] = useState(false);

  const [deltaGenRate, setDeltaGenRate] = useState<number>(0.0);
  const [deltaUsagePct, setDeltaUsagePct] = useState<number>(0.0);
  const [customKwh, setCustomKwh] = useState<string>("");
  const [sensitivityResult, setSensitivityResult] = useState<RateSensitivityResponse | null>(null);
  const [simulatingSensitivity, setSimulatingSensitivity] = useState(false);

  const [settingsForm, setSettingsForm] = useState<TEIBillingProfile>({
    customer_class: "Residential",
    billing_cycle_day: 25,
    connection_type: "behind_meter",
    is_lifeline_eligible: false,
    is_senior_eligible: false,
    is_prompt_payment_eligible: false,
    previous_unpaid_balance: 0.0,
    payments_received: 0.0,
    forecast_method: "7day"
  });

  const getCyclePreview = (day: number) => {
    const d = Math.max(1, Math.min(31, Number(day) || 25));
    const now = new Date();
    const curYear = now.getFullYear();
    const curMonth = now.getMonth();
    const curDay = now.getDate();

    let startYear = curYear;
    let startMonth = curMonth;
    let endYear = curYear;
    let endMonth = curMonth;

    if (curDay >= d) {
      startYear = curYear;
      startMonth = curMonth;
      endMonth = curMonth + 1;
      if (endMonth > 11) {
        endMonth = 0;
        endYear = curYear + 1;
      }
    } else {
      startMonth = curMonth - 1;
      if (startMonth < 0) {
        startMonth = 11;
        startYear = curYear - 1;
      }
      endMonth = curMonth;
      endYear = curYear;
    }

    const maxDaysStart = new Date(startYear, startMonth + 1, 0).getDate();
    const maxDaysEnd = new Date(endYear, endMonth + 1, 0).getDate();
    const actualStartDay = Math.min(d, maxDaysStart);
    const actualEndDay = Math.min(d, maxDaysEnd);

    const startDate = new Date(startYear, startMonth, actualStartDay);
    const endDate = new Date(endYear, endMonth, actualEndDay);

    const formatD = (date: Date) => formatDateMMDDYYYY(date);

    return {
      startFormatted: formatD(startDate),
      endFormatted: formatD(endDate)
    };
  };

  const [billForm, setBillForm] = useState({
    billing_period_start: "",
    billing_period_end: "",
    billed_kwh: 0,
    actual_amount_due: 0,
    predicted_amount_due: 0,
    notes: ""
  });

  const [manualRateForm, setManualRateForm] = useState({
    effective_month: "2026-11",
    customer_class: "Residential",
    generation_charge: 6.7489,
    generation_vat: 0.7112,
    distribution_charge: 1.4520,
    transmission_charge: 0.8524,
    system_loss_charge: 0.5412
  });

  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    generation_transmission: true,
    distribution: true,
    other: true,
    taxes: true,
    discounts: true
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [fData, pData, prof, rList, bList] = await Promise.all([
        api.getBillingOverview(activeDatasetId || undefined),
        api.getBillingProgress(activeDatasetId || undefined),
        api.getBillingProfile(),
        api.getBillingRates(),
        api.getHistoricalBills()
      ]);
      setForecast(fData);
      setProgressData(pData);
      setSettingsForm(prof);
      setRates(rList);
      setHistoryBills(bList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeDatasetId]);

  const handleCheckRatesNow = async () => {
    setCheckingRates(true);
    setCheckMessage(null);
    try {
      const res = await api.checkBillingRatesNow();
      setCheckMessage(res.message);
      await loadData();
    } catch (err: any) {
      setCheckMessage("Unable to connect to TEI rate server. Retained latest verified schedule.");
    } finally {
      setCheckingRates(false);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.updateBillingProfile(settingsForm);
      setIsSettingsOpen(false);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddBill = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.addHistoricalBill({
        billing_period_start: billForm.billing_period_start,
        billing_period_end: billForm.billing_period_end,
        billed_kwh: Number(billForm.billed_kwh),
        actual_amount_due: Number(billForm.actual_amount_due),
        predicted_amount_due: billForm.predicted_amount_due ? Number(billForm.predicted_amount_due) : undefined,
        notes: billForm.notes
      });
      setIsAddBillOpen(false);
      const bList = await api.getHistoricalBills();
      setHistoryBills(bList);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteBill = async (id: string) => {
    try {
      await api.deleteHistoricalBill(id);
      const bList = await api.getHistoricalBills();
      setHistoryBills(bList);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddManualRate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.addManualRateSchedule({
        effective_month: manualRateForm.effective_month,
        customer_class: manualRateForm.customer_class,
        generation_charge: Number(manualRateForm.generation_charge),
        generation_vat: Number(manualRateForm.generation_vat),
        distribution_charge: Number(manualRateForm.distribution_charge),
        transmission_charge: Number(manualRateForm.transmission_charge),
        system_loss_charge: Number(manualRateForm.system_loss_charge)
      });
      setIsManualRateOpen(false);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunSensitivity = async (deltaGen: number, deltaUsage: number, customVal?: string) => {
    setSimulatingSensitivity(true);
    setDeltaGenRate(deltaGen);
    setDeltaUsagePct(deltaUsage);
    try {
      const parsedCustom = customVal && customVal.trim() !== "" ? Number(customVal) : undefined;
      const res = await api.calculateRateSensitivity({
        delta_gen_rate: deltaGen,
        delta_usage_pct: deltaUsage,
        custom_kwh: parsedCustom
      }, activeDatasetId || undefined);
      setSensitivityResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setSimulatingSensitivity(false);
    }
  };

  const toggleCategory = (cat: string) => {
    setExpandedCategories(prev => ({ ...prev, [cat]: !prev[cat] }));
  };

  const currentStatement: StatementOfAccount | null = forecast ? (
    statementMode === "actual"
      ? forecast.current_so_far_statement
      : statementMode === "lower"
      ? forecast.lower_estimate.statement
      : statementMode === "higher"
      ? forecast.higher_estimate.statement
      : forecast.expected_estimate.statement
  ) : null;

  const chartTimeline = progressData?.timeline || [];
  const progressOption = {
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        if (!params || params.length === 0) return "";
        const item = chartTimeline[params[0].dataIndex];
        if (!item) return "";
        let html = `<div class="font-sans text-xs"><b>${formatDateMMDDYYYY(item.date)}</b><br/>`;
        if (item.is_actual) {
          html += `<span class="text-emerald-600">● Observed: ${item.cumulative_kwh_actual?.toFixed(1)} kWh (₱${item.cumulative_cost_actual?.toFixed(2)})</span><br/>`;
        } else {
          html += `<span class="text-amber-600">-- Projected: ${item.cumulative_kwh_expected?.toFixed(1)} kWh (₱${item.cumulative_cost_expected?.toFixed(2)})</span><br/>`;
        }
        if (item.is_today) html += `<span class="text-blue-500 font-semibold">Today's Observation</span><br/>`;
        if (item.is_meter_reading) html += `<span class="text-purple-600 font-semibold">Meter Reading Day</span><br/>`;
        html += `</div>`;
        return html;
      }
    },
    legend: {
      data: ["Electricity Purchased (kWh)", "Estimated Cost (₱)"],
      bottom: 0,
      textStyle: { color: "#64748b" }
    },
    grid: { left: "4%", right: "4%", top: "8%", bottom: "16%", containLabel: true },
    xAxis: {
      type: "category",
      data: chartTimeline.map(t => t.day_label),
      axisLine: { lineStyle: { color: "#94a3b8" } }
    },
    yAxis: [
      {
        type: "value",
        name: "Electricity (kWh)",
        axisLine: { lineStyle: { color: "#94a3b8" } },
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
      },
      {
        type: "value",
        name: "Estimated Cost (₱)",
        axisLine: { lineStyle: { color: "#94a3b8" } },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: "Electricity Purchased (kWh)",
        type: "line",
        smooth: true,
        data: chartTimeline.map(t => t.is_actual ? t.cumulative_kwh_actual : t.cumulative_kwh_expected),
        itemStyle: { color: theme.colors.coral },
        lineStyle: {
          width: 3,
          color: theme.colors.coral,
          type: chartTimeline.some(t => !t.is_actual) ? "solid" : "solid"
        }
      },
      {
        name: "Estimated Cost (₱)",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: chartTimeline.map(t => t.is_actual ? t.cumulative_cost_actual : t.cumulative_cost_expected),
        itemStyle: { color: theme.colors.solar },
        lineStyle: { width: 2.5, color: theme.colors.solar }
      }
    ]
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <ReceiptText className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Bill Intelligence — TEI Electricity Statement Estimator
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Local tariff monitoring, monthly electricity bill prediction, and solar savings reconciliation.
          </p>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700">
              <Calendar className="w-3.5 h-3.5 text-amber-600" />
              <span>
                Meter Reading: <strong>Day {settingsForm.billing_cycle_day || 25}</strong> ({forecast?.billing_cycle_start ? formatDateMMDDYYYY(forecast.billing_cycle_start) : "10/25/2026"} – {forecast?.billing_cycle_end ? formatDateMMDDYYYY(forecast.billing_cycle_end) : "11/25/2026"})
              </span>
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Day {forecast?.days_elapsed || 0} of {forecast?.cycle_total_days || 31} ({forecast?.days_remaining || 0} days remaining)
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleCheckRatesNow}
            disabled={checkingRates}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${checkingRates ? 'animate-spin text-amber-500' : 'text-slate-400'}`} />
            <span>{checkingRates ? "Checking TEI..." : "Check TEI Rates"}</span>
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-slate-200 text-white dark:text-slate-900 transition-colors flex items-center gap-1.5 shadow-xs"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Billing Settings</span>
          </button>
        </div>
      </div>

      <div className="p-3 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-600 dark:text-slate-400">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-slate-400 shrink-0" />
          <span>
            Projections calculated using verified published tariffs and active cycle meter readings.
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-500">
          <span>Schedule: {forecast?.active_rate_effective_month || "October 2026"}</span>
          {checkMessage && (
            <span className="text-emerald-600 dark:text-emerald-400 font-sans font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              {checkMessage}
            </span>
          )}
        </div>
      </div>

      {forecast?.rate_change_alert && (
        <div className="p-3.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg flex items-start gap-3 text-xs text-slate-700 dark:text-slate-300">
          <TrendingUp className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="font-semibold text-slate-900 dark:text-slate-100">
              New TEI Tariff Published: {forecast.rate_change_alert.effective_month}
            </div>
            <div className="mt-1 flex flex-wrap gap-4 text-[11px] font-mono text-slate-500">
              <span>Previous: ₱{forecast.rate_change_alert.previous_rate.toFixed(4)}/kWh</span>
              <span>New: ₱{forecast.rate_change_alert.new_rate.toFixed(4)}/kWh</span>
              <span>Diff: ₱{forecast.rate_change_alert.difference_per_kwh > 0 ? "+" : ""}{forecast.rate_change_alert.difference_per_kwh.toFixed(4)}/kWh</span>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-2 card-stagger-1 interactive-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Estimated Next TEI Bill
            </span>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
              Forecast
            </span>
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
            ₱{forecast?.expected_estimate.estimated_total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || "0.00"}
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <span>Range: ₱{forecast?.lower_estimate.estimated_total_amount.toFixed(0)} - ₱{forecast?.higher_estimate.estimated_total_amount.toFixed(0)}</span>
            <span className="text-amber-600 dark:text-amber-400 font-medium">{forecast?.days_remaining || 0} days remaining</span>
          </div>
        </div>

        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-2 card-stagger-2 interactive-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Electricity Bought So Far
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Day {forecast?.days_elapsed || 0} of {forecast?.cycle_total_days || 30}
            </span>
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
            {forecast?.actual_imported_kwh.toFixed(1) || "0.0"} <span className="text-sm font-normal text-slate-500">kWh</span>
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <span>Projected total: {forecast?.expected_estimate.total_projected_kwh.toFixed(1)} kWh</span>
            <span>{forecast?.expected_estimate.daily_import_rate_kwh.toFixed(1)} kWh/day</span>
          </div>
        </div>

        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-2 card-stagger-3 interactive-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Solar Savings This Cycle
            </span>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400">
              {forecast?.solar_savings.savings_percentage.toFixed(0)}% Lower
            </span>
          </div>
          <div className="text-2xl font-bold text-amber-600 dark:text-amber-400 tabular-nums">
            ₱{forecast?.solar_savings.savings_pesos.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || "0.00"}
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <span>Bill without solar: ₱{forecast?.solar_savings.bill_without_solar.toFixed(2)}</span>
            <span>Avoided {forecast?.solar_savings.avoided_grid_kwh.toFixed(0)} kWh</span>
          </div>
        </div>

        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Active TEI Generation Rate
            </span>
            <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
              Verified
            </span>
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
            ₱{forecast?.active_generation_charge.toFixed(5) || "6.74890"} <span className="text-sm font-normal text-slate-500">/kWh</span>
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <span>+ Gen VAT ₱{forecast?.active_generation_vat.toFixed(5)}</span>
            <span>Cycle: {forecast?.billing_cycle_start ? formatDateMMDDYYYY(forecast.billing_cycle_start) : "10/25/2026"} to {forecast?.billing_cycle_end ? formatDateMMDDYYYY(forecast.billing_cycle_end) : "11/25/2026"}</span>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Electricity Bill Progression Across Current Billing Cycle
            </h2>
            <p className="text-xs text-slate-500">
              Tracking observed electricity purchases and projected costs toward your next meter reading date ({forecast?.next_meter_reading_date ? formatDateMMDDYYYY(forecast.next_meter_reading_date) : "11/25/2026"}).
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-coral-500 inline-block" style={{ backgroundColor: theme.colors.coral }}></span>
              Observed Purchases
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" style={{ backgroundColor: theme.colors.solar }}></span>
              Estimated Cost (₱)
            </span>
          </div>
        </div>
        <EChartComponent option={progressOption} height={280} loading={loading} />
      </div>

      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          onClick={() => setActiveTab("statement")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "statement"
              ? "border-amber-600 text-amber-600 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
          }`}
        >
          <ReceiptText className="w-4 h-4" />
          <span>Statement of Account Simulator</span>
        </button>

        <button
          onClick={() => setActiveTab("savings")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "savings"
              ? "border-amber-600 text-amber-600 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
          }`}
        >
          <Sun className="w-4 h-4" />
          <span>Solar Savings vs No-Solar Baseline</span>
        </button>

        <button
          onClick={() => setActiveTab("sensitivity")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "sensitivity"
              ? "border-amber-600 text-amber-600 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Rate Sensitivity Calculator</span>
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "history"
              ? "border-amber-600 text-amber-600 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Past Bills & Forecast Accuracy</span>
        </button>

        <button
          onClick={() => setActiveTab("rates")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "rates"
              ? "border-amber-600 text-amber-600 dark:text-amber-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>TEI Rate Schedule Archive</span>
        </button>
      </div>

      {activeTab === "statement" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-500">Statement View Mode:</span>
              <div className="flex bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-xs">
                <button
                  onClick={() => setStatementMode("expected")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    statementMode === "expected"
                      ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400"
                  }`}
                >
                  Expected Full Month ({forecast?.expected_estimate.total_projected_kwh.toFixed(1)} kWh)
                </button>
                <button
                  onClick={() => setStatementMode("actual")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    statementMode === "actual"
                      ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400"
                  }`}
                >
                  Purchased So Far ({forecast?.actual_imported_kwh.toFixed(1)} kWh)
                </button>
                <button
                  onClick={() => setStatementMode("lower")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    statementMode === "lower"
                      ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400"
                  }`}
                >
                  Lower Estimate ({forecast?.lower_estimate.total_projected_kwh.toFixed(1)} kWh)
                </button>
                <button
                  onClick={() => setStatementMode("higher")}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    statementMode === "higher"
                      ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm font-semibold"
                      : "text-slate-600 dark:text-slate-400"
                  }`}
                >
                  Higher Estimate ({forecast?.higher_estimate.total_projected_kwh.toFixed(1)} kWh)
                </button>
              </div>
            </div>

            <div className="text-xs text-slate-500">
              Effective Average Rate: <span className="font-semibold text-slate-800 dark:text-slate-200">₱{currentStatement?.effective_average_rate_per_kwh.toFixed(4)}/kWh</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                  Itemized Electricity Charges & Taxes
                </h3>
                <p className="text-[11px] text-slate-500">
                  Calculated using TEI {currentStatement?.effective_rate_schedule_month} schedule ({currentStatement?.customer_class} Class).
                </p>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-mono text-slate-400">Total Billed:</span>
                <span className="ml-1.5 text-xs font-bold text-slate-900 dark:text-slate-100">{currentStatement?.billed_kwh.toFixed(2)} kWh</span>
              </div>
            </div>

            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              <div className="p-4">
                <div
                  onClick={() => toggleCategory("generation_transmission")}
                  className="flex items-center justify-between cursor-pointer py-1 font-semibold text-xs text-slate-800 dark:text-slate-200 select-none"
                >
                  <span className="flex items-center gap-1.5">
                    {expandedCategories.generation_transmission ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    Generation & Transmission Charges
                  </span>
                  <span className="font-bold tabular-nums">₱{currentStatement?.generation_transmission_charges.toFixed(2)}</span>
                </div>

                {expandedCategories.generation_transmission && (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="text-[11px] text-slate-400 border-b border-slate-100 dark:border-slate-800">
                        <tr>
                          <th className="py-2 font-medium">Charge Component</th>
                          <th className="py-2 font-medium">Applied Rate</th>
                          <th className="py-2 font-medium">VAT Treatment</th>
                          <th className="py-2 font-medium text-right">Amount (₱)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50 dark:divide-slate-800/60">
                        {currentStatement?.line_items
                          .filter(i => i.category === "generation_transmission")
                          .map(item => (
                            <tr key={item.component_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                              <td className="py-2.5 pr-2">
                                <div className="font-medium text-slate-800 dark:text-slate-200">{item.name}</div>
                                <div className="text-[10px] text-slate-400">{viewMode === 'detailed' ? item.formula : item.explanation}</div>
                              </td>
                              <td className="py-2.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                                ₱{item.rate_applied.toFixed(5)}/{item.rate_unit.replace("₱/", "")}
                              </td>
                              <td className="py-2.5">
                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                  item.vat_treatment === "fixed_rate" ? "bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400" :
                                  item.vat_treatment === "exempt" ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400" :
                                  "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                                }`}>
                                  {item.vat_treatment === "fixed_rate" ? "Separate VAT ₱0.7112/kWh" : item.vat_treatment === "exempt" ? "VAT Exempt (2026 Rules)" : "Standard 12% VAT"}
                                </span>
                              </td>
                              <td className="py-2.5 text-right font-semibold tabular-nums text-slate-800 dark:text-slate-200">
                                ₱{item.amount.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="p-4">
                <div
                  onClick={() => toggleCategory("distribution")}
                  className="flex items-center justify-between cursor-pointer py-1 font-semibold text-xs text-slate-800 dark:text-slate-200 select-none"
                >
                  <span className="flex items-center gap-1.5">
                    {expandedCategories.distribution ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    Distribution, Supply & Metering Charges
                  </span>
                  <span className="font-bold tabular-nums">₱{currentStatement?.distribution_charges.toFixed(2)}</span>
                </div>

                {expandedCategories.distribution && (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="text-[11px] text-slate-400 border-b border-slate-100 dark:border-slate-800">
                        <tr>
                          <th className="py-2 font-medium">Charge Component</th>
                          <th className="py-2 font-medium">Applied Rate</th>
                          <th className="py-2 font-medium">VAT Treatment</th>
                          <th className="py-2 font-medium text-right">Amount (₱)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50 dark:divide-slate-800/60">
                        {currentStatement?.line_items
                          .filter(i => i.category === "distribution")
                          .map(item => (
                            <tr key={item.component_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                              <td className="py-2.5 pr-2">
                                <div className="font-medium text-slate-800 dark:text-slate-200">{item.name}</div>
                                <div className="text-[10px] text-slate-400">{viewMode === 'detailed' ? item.formula : item.explanation}</div>
                              </td>
                              <td className="py-2.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                                ₱{item.rate_applied.toFixed(5)}/{item.rate_unit.replace("₱/", "")}
                              </td>
                              <td className="py-2.5">
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                                  Standard 12% VAT
                                </span>
                              </td>
                              <td className="py-2.5 text-right font-semibold tabular-nums text-slate-800 dark:text-slate-200">
                                ₱{item.amount.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="p-4">
                <div
                  onClick={() => toggleCategory("other")}
                  className="flex items-center justify-between cursor-pointer py-1 font-semibold text-xs text-slate-800 dark:text-slate-200 select-none"
                >
                  <span className="flex items-center gap-1.5">
                    {expandedCategories.other ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    Other Approved Charges & Universal Levies
                  </span>
                  <span className="font-bold tabular-nums">₱{currentStatement?.other_charges.toFixed(2)}</span>
                </div>

                {expandedCategories.other && (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="text-[11px] text-slate-400 border-b border-slate-100 dark:border-slate-800">
                        <tr>
                          <th className="py-2 font-medium">Charge Component</th>
                          <th className="py-2 font-medium">Applied Rate</th>
                          <th className="py-2 font-medium">VAT Treatment</th>
                          <th className="py-2 font-medium text-right">Amount (₱)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50 dark:divide-slate-800/60">
                        {currentStatement?.line_items
                          .filter(i => i.category === "other")
                          .map(item => (
                            <tr key={item.component_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                              <td className="py-2.5 pr-2">
                                <div className="font-medium text-slate-800 dark:text-slate-200">{item.name}</div>
                                <div className="text-[10px] text-slate-400">{viewMode === 'detailed' ? item.formula : item.explanation}</div>
                              </td>
                              <td className="py-2.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                                ₱{item.rate_applied.toFixed(5)}/{item.rate_unit.replace("₱/", "")}
                              </td>
                              <td className="py-2.5">
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
                                  VAT Exempt
                                </span>
                              </td>
                              <td className="py-2.5 text-right font-semibold tabular-nums text-slate-800 dark:text-slate-200">
                                ₱{item.amount.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="p-4">
                <div
                  onClick={() => toggleCategory("taxes")}
                  className="flex items-center justify-between cursor-pointer py-1 font-semibold text-xs text-slate-800 dark:text-slate-200 select-none"
                >
                  <span className="flex items-center gap-1.5">
                    {expandedCategories.taxes ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                    Government Taxes & Local Assessments
                  </span>
                  <span className="font-bold tabular-nums">₱{currentStatement?.government_taxes.toFixed(2)}</span>
                </div>

                {expandedCategories.taxes && (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="text-[11px] text-slate-400 border-b border-slate-100 dark:border-slate-800">
                        <tr>
                          <th className="py-2 font-medium">Tax Component</th>
                          <th className="py-2 font-medium">Rate / Basis</th>
                          <th className="py-2 font-medium">Calculation Rule</th>
                          <th className="py-2 font-medium text-right">Amount (₱)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50 dark:divide-slate-800/60">
                        {currentStatement?.line_items
                          .filter(i => i.category === "taxes")
                          .map(item => (
                            <tr key={item.component_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                              <td className="py-2.5 pr-2 font-medium text-slate-800 dark:text-slate-200">
                                {item.name}
                              </td>
                              <td className="py-2.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                                {item.rate_unit === "% of Gross" ? `${(item.rate_applied * 100).toFixed(2)}%` : `₱${item.rate_applied.toFixed(4)}`}
                              </td>
                              <td className="py-2.5 text-[10px] text-slate-500">
                                {item.formula}
                              </td>
                              <td className="py-2.5 text-right font-semibold tabular-nums text-slate-800 dark:text-slate-200">
                                ₱{item.amount.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {currentStatement?.line_items.some(i => i.category === "discounts") && (
                <div className="p-4 bg-emerald-50/30 dark:bg-emerald-950/10">
                  <div
                    onClick={() => toggleCategory("discounts")}
                    className="flex items-center justify-between cursor-pointer py-1 font-semibold text-xs text-emerald-800 dark:text-emerald-300 select-none"
                  >
                    <span className="flex items-center gap-1.5">
                      {expandedCategories.discounts ? <ChevronUp className="w-4 h-4 text-emerald-600" /> : <ChevronDown className="w-4 h-4 text-emerald-600" />}
                      Discounts & Net Metering Solar Credits
                    </span>
                    <span className="font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                      -₱{(currentStatement.discounts + currentStatement.net_metering_credits).toFixed(2)}
                    </span>
                  </div>

                  {expandedCategories.discounts && (
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <tbody className="divide-y divide-emerald-100/60 dark:divide-emerald-900/40">
                          {currentStatement.line_items
                            .filter(i => i.category === "discounts")
                            .map(item => (
                              <tr key={item.component_id}>
                                <td className="py-2 pr-2">
                                  <div className="font-medium text-emerald-800 dark:text-emerald-300">{item.name}</div>
                                  <div className="text-[10px] text-emerald-600 dark:text-emerald-400">{item.formula}</div>
                                </td>
                                <td className="py-2 text-right font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
                                  -₱{Math.abs(item.amount).toFixed(2)}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="p-5 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
                <span>Subtotal Electricity Charges (Generation, Transmission, Distribution, Universal):</span>
                <span className="font-medium tabular-nums text-slate-800 dark:text-slate-200">₱{currentStatement?.subtotal_electricity_charges.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
                <span>Government Taxes (VAT, Franchise, RPT):</span>
                <span className="font-medium tabular-nums text-slate-800 dark:text-slate-200">+₱{currentStatement?.government_taxes.toFixed(2)}</span>
              </div>
              {(currentStatement?.discounts || 0) + (currentStatement?.net_metering_credits || 0) > 0 && (
                <div className="flex items-center justify-between text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                  <span>Discounts & Solar Export Credits:</span>
                  <span className="tabular-nums">-₱{((currentStatement?.discounts || 0) + (currentStatement?.net_metering_credits || 0)).toFixed(2)}</span>
                </div>
              )}

              <div className="pt-2 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between text-sm font-semibold text-slate-800 dark:text-slate-200">
                <span>Total Current Month Electricity Charges:</span>
                <span className="tabular-nums">₱{currentStatement?.total_current_charges.toFixed(2)}</span>
              </div>

              {(currentStatement?.previous_unpaid_balance || 0) > 0 && (
                <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
                  <span>Previous Unpaid Account Balance:</span>
                  <span className="tabular-nums">+₱{currentStatement?.previous_unpaid_balance.toFixed(2)}</span>
                </div>
              )}

              {(currentStatement?.payments_received || 0) > 0 && (
                <div className="flex items-center justify-between text-xs text-emerald-600 dark:text-emerald-400 pt-1">
                  <span>Payments Received & Recorded:</span>
                  <span className="tabular-nums">-₱{currentStatement?.payments_received.toFixed(2)}</span>
                </div>
              )}

              <div className="pt-3 border-t-2 border-slate-900 dark:border-slate-100 flex items-center justify-between">
                <div>
                  <div className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Estimated Total Amount Due:
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Payment Due Date: Approximate 10 days after expected meter reading
                  </div>
                </div>
                <div className="text-2xl font-black text-amber-600 dark:text-amber-400 tabular-nums">
                  ₱{currentStatement?.total_amount_due.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "savings" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="p-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Modeled Bill Without Solar
              </span>
              <div className="text-3xl font-bold text-slate-800 dark:text-slate-200 tabular-nums">
                ₱{forecast?.solar_savings.bill_without_solar.toFixed(2)}
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Cost if your entire household demand ({forecast?.solar_savings.household_total_demand_kwh.toFixed(1)} kWh) had been purchased directly from TEI without solar panels or battery.
              </p>
            </div>

            <div className="p-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Actual / Projected Bill With Solar
              </span>
              <div className="text-3xl font-bold text-slate-800 dark:text-slate-200 tabular-nums">
                ₱{forecast?.solar_savings.bill_with_solar.toFixed(2)}
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Calculated TEI bill based on only {forecast?.solar_savings.actual_imported_kwh.toFixed(1)} kWh imported from the grid after solar self-consumption and battery support.
              </p>
            </div>

            <div className="p-6 bg-amber-50/50 dark:bg-amber-950/20 rounded-xl border border-amber-200 dark:border-amber-900 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                  Total Avoided Electricity Cost
                </span>
                <span className="text-xs font-bold text-amber-700 dark:text-amber-300">
                  {forecast?.solar_savings.savings_percentage.toFixed(0)}% Off
                </span>
              </div>
              <div className="text-3xl font-black text-amber-700 dark:text-amber-400 tabular-nums">
                ₱{forecast?.solar_savings.savings_pesos.toFixed(2)}
              </div>
              <p className="text-xs text-amber-900/80 dark:text-amber-200/80 leading-relaxed">
                Net pesos retained in your pocket this billing period by generating your own electricity.
              </p>
            </div>
          </div>

          <div className="p-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Where Did Your Avoided Electricity Costs Come From?
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800 space-y-2">
                <div className="flex items-center gap-2">
                  <Sun className="w-4 h-4 text-amber-500" />
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    Direct Daytime Solar Self-Consumption
                  </span>
                </div>
                <div className="text-xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                  ₱{forecast?.solar_savings.direct_solar_savings_pesos.toFixed(2)}
                </div>
                <p className="text-[11px] text-slate-500">
                  Supplied {forecast?.solar_savings.direct_solar_used_kwh.toFixed(1)} kWh directly to your appliances while the sun was shining, preventing TEI meter purchases.
                </p>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800 space-y-2">
                <div className="flex items-center gap-2">
                  <BatteryCharging className="w-4 h-4 text-teal-500" />
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    Nighttime Battery Discharge Support
                  </span>
                </div>
                <div className="text-xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                  ₱{forecast?.solar_savings.battery_savings_pesos.toFixed(2)}
                </div>
                <p className="text-[11px] text-slate-500">
                  Supplied {forecast?.solar_savings.battery_discharged_kwh.toFixed(1)} kWh from stored battery energy during the evening and night when solar panels were dark.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "sensitivity" && (
        <div className="space-y-6">
          <div className="p-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                TEI Rate Change & Electricity Usage Sensitivity Simulator
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Test how potential TEI Generation Charge adjustments or changes in your household consumption will affect your final monthly bill.
              </p>
            </div>

            <div className={`grid grid-cols-1 md:grid-cols-3 gap-6 transition-opacity ${simulatingSensitivity ? "opacity-50 pointer-events-none" : ""}`}>
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Generation Charge Adjustment (₱/kWh)
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {[-1.0, -0.5, 0.0, 0.5, 1.0, 2.0].map(val => (
                    <button
                      key={val}
                      onClick={() => handleRunSensitivity(val, deltaUsagePct, customKwh)}
                      className={`px-2.5 py-1 text-xs rounded font-mono ${
                        deltaGenRate === val
                          ? "bg-amber-600 text-white font-bold"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200"
                      }`}
                    >
                      {val > 0 ? `+₱${val.toFixed(2)}` : val < 0 ? `-₱${Math.abs(val).toFixed(2)}` : "Current"}
                    </button>
                  ))}
                </div>
                <div className="text-[11px] text-slate-500">
                  Tested Generation Rate: ₱{((forecast?.active_generation_charge || 6.7489) + deltaGenRate).toFixed(5)}/kWh
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Household Grid Purchases Shift (%)
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {[-20, -10, 0, 10, 20].map(pct => (
                    <button
                      key={pct}
                      onClick={() => handleRunSensitivity(deltaGenRate, pct, customKwh)}
                      className={`px-2.5 py-1 text-xs rounded font-mono ${
                        deltaUsagePct === pct && !customKwh
                          ? "bg-amber-600 text-white font-bold"
                          : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200"
                      }`}
                    >
                      {pct > 0 ? `+${pct}%` : `${pct}%`}
                    </button>
                  ))}
                </div>
                <div className="text-[11px] text-slate-500">
                  Simulate energy conservation or added appliance load.
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Or Test Specific Monthly Import (kWh)
                </label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    placeholder="e.g. 250"
                    value={customKwh}
                    onChange={(e) => {
                      setCustomKwh(e.target.value);
                      handleRunSensitivity(deltaGenRate, deltaUsagePct, e.target.value);
                    }}
                    className="w-full text-xs px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-amber-500 font-mono"
                  />
                  {customKwh && (
                    <button
                      onClick={() => {
                        setCustomKwh("");
                        handleRunSensitivity(deltaGenRate, deltaUsagePct, "");
                      }}
                      className="px-2 py-1 text-xs text-slate-400 hover:text-slate-600"
                    >
                      Clear
                    </button>
                  )}
                </div>
                <div className="text-[11px] text-slate-500">
                  Override forecast with a round consumption target.
                </div>
              </div>
            </div>

            {sensitivityResult && (
              <div className="p-5 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                    Simulation Comparison Result
                  </span>
                  <span className="text-[11px] font-mono text-slate-500">
                    Tested Billed Energy: {sensitivityResult.simulated_kwh.toFixed(1)} kWh (Baseline: {sensitivityResult.baseline_kwh.toFixed(1)} kWh)
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[11px] text-slate-500">Baseline Expected Bill</span>
                    <div className="text-xl font-bold text-slate-800 dark:text-slate-200 tabular-nums mt-1">
                      ₱{sensitivityResult.baseline_bill.toFixed(2)}
                    </div>
                  </div>

                  <div className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[11px] text-slate-500">Simulated Outcome</span>
                    <div className="text-xl font-bold text-slate-800 dark:text-slate-200 tabular-nums mt-1">
                      ₱{sensitivityResult.simulated_bill.toFixed(2)}
                    </div>
                  </div>

                  <div className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[11px] text-slate-500">Projected Net Difference</span>
                    <div className={`text-xl font-bold tabular-nums mt-1 ${
                      sensitivityResult.difference_pesos > 0 ? "text-coral-600 dark:text-coral-400" :
                      sensitivityResult.difference_pesos < 0 ? "text-emerald-600 dark:text-emerald-400" :
                      "text-slate-800 dark:text-slate-200"
                    }`}>
                      {sensitivityResult.difference_pesos > 0 ? "+" : ""}₱{sensitivityResult.difference_pesos.toFixed(2)} ({sensitivityResult.difference_percentage > 0 ? "+" : ""}{sensitivityResult.difference_percentage.toFixed(1)}%)
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "history" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Past Statements of Account & Prediction Accuracy Log
              </h3>
              <p className="text-xs text-slate-500">
                Compare actual paper bills received from TEI against SolarScope predictions.
              </p>
            </div>
            <button
              onClick={() => setIsAddBillOpen(true)}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-200 transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Record Past Bill</span>
            </button>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            {historyBills.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No past statements recorded yet. Click "Record Past Bill" to log your previous TEI statements and audit forecasting accuracy.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Billing Period</th>
                      <th className="px-4 py-3 font-semibold">Billed Energy</th>
                      <th className="px-4 py-3 font-semibold">Actual TEI Bill</th>
                      <th className="px-4 py-3 font-semibold">Predicted Bill</th>
                      <th className="px-4 py-3 font-semibold">Variance (₱ / %)</th>
                      <th className="px-4 py-3 font-semibold">Accuracy</th>
                      <th className="px-4 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {historyBills.map(b => (
                      <tr key={b.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                        <td className="px-4 py-3 font-medium text-slate-800 dark:text-slate-200">
                          {b.billing_period_start} to {b.billing_period_end}
                        </td>
                        <td className="px-4 py-3 font-mono">{b.billed_kwh.toFixed(1)} kWh</td>
                        <td className="px-4 py-3 font-bold tabular-nums">₱{b.actual_amount_due.toFixed(2)}</td>
                        <td className="px-4 py-3 tabular-nums text-slate-600 dark:text-slate-400">
                          {b.predicted_amount_due ? `₱${b.predicted_amount_due.toFixed(2)}` : "N/A"}
                        </td>
                        <td className="px-4 py-3 font-mono">
                          {b.variance_pesos !== null ? (
                            <span className={b.variance_pesos > 0 ? "text-amber-600" : "text-emerald-600"}>
                              {b.variance_pesos > 0 ? "+" : ""}₱{b.variance_pesos.toFixed(2)} ({b.variance_percent}%)
                            </span>
                          ) : "N/A"}
                        </td>
                        <td className="px-4 py-3">
                          {b.accuracy_percent !== null ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
                              {b.accuracy_percent}% Accurate
                            </span>
                          ) : "N/A"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDeleteBill(b.id)}
                            className="p-1 text-slate-400 hover:text-red-600 transition-colors"
                            title="Delete Record"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "rates" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                TEI Rate Schedule Archive & Monitoring Records
              </h3>
              <p className="text-xs text-slate-500">
                All rate schedule versions extracted from Tarlac Electric Inc. and verified locally.
              </p>
            </div>
            <button
              onClick={() => setIsManualRateOpen(true)}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Custom Rate Schedule</span>
            </button>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Effective Month</th>
                    <th className="px-4 py-3 font-semibold">Customer Class</th>
                    <th className="px-4 py-3 font-semibold">Generation Charge</th>
                    <th className="px-4 py-3 font-semibold">Components</th>
                    <th className="px-4 py-3 font-semibold">Verification Status</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {rates.map(r => (
                    <tr key={r.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                      <td className="px-4 py-3 font-semibold text-slate-800 dark:text-slate-200">
                        {r.effective_month}
                      </td>
                      <td className="px-4 py-3">{r.customer_class}</td>
                      <td className="px-4 py-3 font-mono font-bold tabular-nums">
                        ₱{r.generation_charge.toFixed(5)}/kWh
                      </td>
                      <td className="px-4 py-3 text-slate-500">{r.components_count} charges</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          r.verification_status === "verified"
                            ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400"
                            : "bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400"
                        }`}>
                          {r.verification_status === "verified" ? "Officially Verified" : "Manual / Custom"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {r.is_active ? (
                          <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Active Schedule
                          </span>
                        ) : (
                          <span className="text-slate-400 text-[10px]">Archived</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-[11px] text-slate-400 truncate max-w-xs">
                        {r.source_url}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Settings className="w-4 h-4 text-amber-600" />
                <span>My TEI Billing Settings & Customer Profile</span>
              </h3>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveSettings} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Customer Class
                  </label>
                  <select
                    value={settingsForm.customer_class}
                    onChange={(e) => setSettingsForm({ ...settingsForm, customer_class: e.target.value })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                  >
                    <option value="Residential">Residential</option>
                    <option value="Small Commercial">Small Commercial</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                      Monthly Meter Reading Day
                    </label>
                    <span className="text-[10px] text-slate-500 font-mono">Day {settingsForm.billing_cycle_day || 25}</span>
                  </div>
                  <input
                    type="number"
                    min="1"
                    max="31"
                    value={settingsForm.billing_cycle_day}
                    onChange={(e) => setSettingsForm({ ...settingsForm, billing_cycle_day: Math.max(1, Math.min(31, Number(e.target.value))) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono text-xs"
                    placeholder="Enter day of month (e.g. 25)"
                  />
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg space-y-1">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                  <Calendar className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  <span>
                    Active Cycle: {getCyclePreview(settingsForm.billing_cycle_day).startFormatted} to {getCyclePreview(settingsForm.billing_cycle_day).endFormatted}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  All electricity purchases and solar savings will be integrated strictly from the <strong>{settingsForm.billing_cycle_day}th of the month</strong> to the <strong>{settingsForm.billing_cycle_day}th of the next month</strong>. Next meter reading: <strong>{getCyclePreview(settingsForm.billing_cycle_day).endFormatted}</strong>.
                </p>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Solar Grid Connection Type
                </label>
                <select
                  value={settingsForm.connection_type}
                  onChange={(e) => setSettingsForm({ ...settingsForm, connection_type: e.target.value })}
                  className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                >
                  <option value="behind_meter">Behind-the-Meter (Zero Export / Non-credited)</option>
                  <option value="net_metering">Approved TEI Net Metering (Export Credited at Gen Rate)</option>
                  <option value="export_uncertain">Exporting with Pending Billing Agreement</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Previous Meter Reading (kWh)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={settingsForm.prev_meter_reading ?? ""}
                    onChange={(e) => setSettingsForm({ ...settingsForm, prev_meter_reading: e.target.value ? Number(e.target.value) : null })}
                    placeholder="e.g. 14250.0"
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Latest Meter Reading (kWh)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={settingsForm.latest_meter_reading ?? ""}
                    onChange={(e) => setSettingsForm({ ...settingsForm, latest_meter_reading: e.target.value ? Number(e.target.value) : null })}
                    placeholder="e.g. 14450.0"
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Remaining Days Projection Method
                </label>
                <select
                  value={settingsForm.forecast_method}
                  onChange={(e) => setSettingsForm({ ...settingsForm, forecast_method: e.target.value })}
                  className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                >
                  <option value="7day">Recent 7-Day Average (Responsive to Weather & Shifts)</option>
                  <option value="14day">Recent 14-Day Average (Balanced Horizon)</option>
                  <option value="30day">Recent 30-Day Average (Smoothed Baseline)</option>
                </select>
              </div>

              <div className="space-y-2 border-t border-slate-100 dark:border-slate-800 pt-3">
                <span className="text-[11px] font-bold text-slate-800 dark:text-slate-200 block">
                  Eligible Discounts & Subsidies
                </span>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settingsForm.is_lifeline_eligible}
                    onChange={(e) => setSettingsForm({ ...settingsForm, is_lifeline_eligible: e.target.checked })}
                    className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                  />
                  <span>Lifeline Assistance Discount (applies only if registered and consumption ≤ 100 kWh)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settingsForm.is_senior_eligible}
                    onChange={(e) => setSettingsForm({ ...settingsForm, is_senior_eligible: e.target.checked })}
                    className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                  />
                  <span>Senior Citizen Discount (5% discount on Gen/Trans/Dist for registered seniors)</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settingsForm.is_prompt_payment_eligible}
                    onChange={(e) => setSettingsForm({ ...settingsForm, is_prompt_payment_eligible: e.target.checked })}
                    className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                  />
                  <span>Prompt Payment Discount (1% on distribution charge when paying within 10 days)</span>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3 border-t border-slate-100 dark:border-slate-800 pt-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Previous Unpaid Balance (₱)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={settingsForm.previous_unpaid_balance}
                    onChange={(e) => setSettingsForm({ ...settingsForm, previous_unpaid_balance: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Payments Made / Credits (₱)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={settingsForm.payments_received}
                    onChange={(e) => setSettingsForm({ ...settingsForm, payments_received: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-sm"
                >
                  Save Settings & Recalculate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isAddBillOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <ReceiptText className="w-4 h-4 text-amber-600" />
                <span>Record Actual Past TEI Statement</span>
              </h3>
              <button
                onClick={() => setIsAddBillOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddBill} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Period Start Date
                  </label>
                  <input
                    type="date"
                    required
                    value={billForm.billing_period_start}
                    onChange={(e) => setBillForm({ ...billForm, billing_period_start: e.target.value })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Period End Date
                  </label>
                  <input
                    type="date"
                    required
                    value={billForm.billing_period_end}
                    onChange={(e) => setBillForm({ ...billForm, billing_period_end: e.target.value })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Billed Energy from Meter (kWh)
                </label>
                <input
                  type="number"
                  step="0.1"
                  required
                  placeholder="e.g. 210.5"
                  value={billForm.billed_kwh || ""}
                  onChange={(e) => setBillForm({ ...billForm, billed_kwh: Number(e.target.value) })}
                  className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Actual Bill Amount (₱)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="e.g. 2450.00"
                    value={billForm.actual_amount_due || ""}
                    onChange={(e) => setBillForm({ ...billForm, actual_amount_due: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono font-bold"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    SolarScope Predicted (₱)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="e.g. 2480.00"
                    value={billForm.predicted_amount_due || ""}
                    onChange={(e) => setBillForm({ ...billForm, predicted_amount_due: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Notes / Bill Statement Reference
                </label>
                <input
                  type="text"
                  placeholder="e.g. Statement #10425, low AC usage"
                  value={billForm.notes}
                  onChange={(e) => setBillForm({ ...billForm, notes: e.target.value })}
                  className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsAddBillOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-sm"
                >
                  Save Bill Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isManualRateOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-600" />
                <span>Enter Custom TEI Rate Schedule</span>
              </h3>
              <button
                onClick={() => setIsManualRateOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddManualRate} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Effective Month (YYYY-MM)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="2026-11"
                    value={manualRateForm.effective_month}
                    onChange={(e) => setManualRateForm({ ...manualRateForm, effective_month: e.target.value })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Customer Class
                  </label>
                  <select
                    value={manualRateForm.customer_class}
                    onChange={(e) => setManualRateForm({ ...manualRateForm, customer_class: e.target.value })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                  >
                    <option value="Residential">Residential</option>
                    <option value="Small Commercial">Small Commercial</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Generation Charge (₱/kWh)
                </label>
                <input
                  type="number"
                  step="0.00001"
                  required
                  value={manualRateForm.generation_charge}
                  onChange={(e) => setManualRateForm({ ...manualRateForm, generation_charge: Number(e.target.value) })}
                  className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono font-bold"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Generation VAT (₱/kWh)
                  </label>
                  <input
                    type="number"
                    step="0.00001"
                    value={manualRateForm.generation_vat}
                    onChange={(e) => setManualRateForm({ ...manualRateForm, generation_vat: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Distribution Charge (₱/kWh)
                  </label>
                  <input
                    type="number"
                    step="0.00001"
                    value={manualRateForm.distribution_charge}
                    onChange={(e) => setManualRateForm({ ...manualRateForm, distribution_charge: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Transmission Charge (₱/kWh)
                  </label>
                  <input
                    type="number"
                    step="0.00001"
                    value={manualRateForm.transmission_charge}
                    onChange={(e) => setManualRateForm({ ...manualRateForm, transmission_charge: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    System Loss Charge (₱/kWh)
                  </label>
                  <input
                    type="number"
                    step="0.00001"
                    value={manualRateForm.system_loss_charge}
                    onChange={(e) => setManualRateForm({ ...manualRateForm, system_loss_charge: Number(e.target.value) })}
                    className="w-full p-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsManualRateOpen(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-sm"
                >
                  Activate Schedule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
