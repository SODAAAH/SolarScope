const API_BASE = "/api";

export async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`API Error [${res.status}]: ${errorText}`);
    }
    return res.json();
  } catch (err: any) {
    if (err.name === "TypeError" && (err.message.includes("fetch") || err.message.includes("network") || err.message.includes("Failed"))) {
      throw new Error("Cannot connect to SolarScope backend at http://127.0.0.1:8000. Ensure backend server is running.");
    }
    throw err;
  }
}

export interface SystemSettings {
  pv_capacity_kwp: number;
  num_modules: number;
  module_wattage: number;
  panel_model?: string;
  panel_tech?: string;
  inverter_model?: string;
  inverter_power_kw: number;
  inverter_serial?: string;
  inverter_max_apparent_va?: number;
  inverter_max_battery_current_a?: number;
  mppt_voltage_min_v?: number;
  mppt_voltage_max_v?: number;
  pv_voltage_max_v?: number;
  mppt_max_current_a?: number;
  logger_serial?: string;
  logger_firmware?: string;
  logger_interval_min?: number;
  battery_model?: string;
  battery_chemistry: string;
  battery_voltage: number;
  battery_ah?: number;
  battery_capacity_kwh: number;
  usable_capacity_kwh: number;
  reserve_soc: number;
  bms_max_charge_a?: number;
  bms_max_discharge_a?: number;
  max_charge_kw: number;
  max_discharge_kw: number;
  battery_efficiency: number;
  import_tariff: number;
  export_tariff: number;
  currency: string;
  timezone: string;
}

export interface ColumnItem {
  original_name: string;
  canonical_name: string | null;
  unit: string | null;
  data_type: string;
  confidence: number;
  sample_values: any[];
  sign_convention: string;
  is_duplicate: boolean;
  duplicate_of: string | null;
  is_inactive: boolean;
}

export interface DatasetPreview {
  dataset_id: string;
  filename: string;
  available_sheets: string[];
  selected_sheet: string;
  total_rows: number;
  columns: ColumnItem[];
  detected_start_time: string | null;
  detected_start_time_12h?: string;
  detected_end_time: string | null;
  detected_end_time_12h?: string;
  preview_rows: Record<string, any>[];
}

export interface SourceItem {
  id: string;
  filename: string;
  file_hash?: string;
  file_format?: string;
  filepath: string;
  sheet_name?: string;
  total_rows: number;
  start_time?: string;
  start_time_12h?: string;
  end_time?: string;
  end_time_12h?: string;
  quality_score: number;
  sampling_interval_median_min?: number;
  gap_count?: number;
  conflict_status?: string;
  is_active: number;
  is_included: number;
  created_at: string;
}

export interface DailySummaryItem {
  date: string;
  status: "COMPLETE" | "PARTIAL" | "INVALID";
  coverage_pct: number;
  record_count: number;
  duration_hours: number;
  longest_gap_min: number;
  pv_kwh: number;
  load_kwh: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
  battery_discharge_kwh: number;
  battery_charge_kwh: number;
  residual_kwh: number;
  self_consumption_ratio: number;
  self_sufficiency_ratio: number;
  grid_dependence_ratio: number;
  start_soc: number;
  end_soc: number;
  min_soc: number;
  max_soc: number;
  avg_soc: number;
  peak_pv_kw: number;
  peak_pv_time_12h: string;
  peak_load_kw: number;
  peak_load_time_12h: string;
  peak_grid_kw: number;
  peak_grid_time_12h: string;
  grid_import_hours: number;
}

export const api = {
  getHealth: () => fetchJson<{ status: string; app: string; version: string; currency: string; time_format: string }>("/health"),
  getSettings: () => fetchJson<SystemSettings>("/settings"),
  updateSettings: (data: SystemSettings) => fetchJson<{ status: string; settings: SystemSettings }>("/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }),
  uploadDataset: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchJson<{ dataset_id: string; filename: string; file_hash?: string; is_duplicate?: boolean; duplicate_of?: string; available_sheets: string[]; selected_sheet: string | null }>("/datasets/upload", {
      method: "POST",
      body: formData,
    });
  },
  uploadDatasetsBatch: async (files: File[]) => {
    const formData = new FormData();
    files.forEach(f => formData.append("files", f));
    return fetchJson<{ total_uploaded: number; files: any[] }>("/datasets/upload_batch", {
      method: "POST",
      body: formData,
    });
  },
  listSources: () => fetchJson<SourceItem[]>("/sources"),
  updateSource: (sourceId: string, payload: { is_included?: boolean; sheet_name?: string }) => {
    return fetchJson<{ status: string; source_id: string }>(`/sources/${sourceId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  deleteSource: (sourceId: string) => {
    return fetchJson<{ status: string; source_id: string }>(`/sources/${sourceId}`, {
      method: "DELETE"
    });
  },
  loadSampleDataset: () => fetchJson<{ dataset_id: string; filename: string; available_sheets: string[]; selected_sheet: string }>("/datasets/load_sample", {
    method: "POST"
  }),
  autoCommitDataset: (datasetId: string) => {
    return fetchJson<{
      status: string;
      dataset_id: string;
      filename: string;
      total_records: number;
      quality_score: number;
      quality_status: string;
      start_time_12h?: string;
      end_time_12h?: string;
    }>(`/datasets/${datasetId}/auto_commit`, {
      method: "POST"
    });
  },
  autoCommitAllDatasets: () => {
    return fetchJson<{ total_processed: number; committed: any[] }>("/datasets/auto_commit_all", {
      method: "POST"
    });
  },
  getPreview: (datasetId: string, sheetName?: string) => {
    const q = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : "";
    return fetchJson<DatasetPreview>(`/datasets/${datasetId}/preview${q}`);
  },
  commitDataset: (datasetId: string, mappings: Record<string, string>, signConventions: Record<string, string>, selectedSheet: string) => {
    return fetchJson<{ status: string; dataset_id: string; total_records: number; quality_score: number; quality_status: string; start_time_12h?: string; end_time_12h?: string }>(`/datasets/${datasetId}/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        selected_sheet: selectedSheet,
        mappings,
        sign_conventions: signConventions
      }),
    });
  },
  getSummary: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/summary`),
  getTimeline: (datasetId: string, date?: string) => {
    const q = date ? `?date=${encodeURIComponent(date)}` : '';
    return fetchJson<{
      timestamps: string[];
      timestamps_12h?: string[];
      timestamps_24h?: string[];
      pv_power_kw: (number | null)[];
      load_power_kw: (number | null)[];
      grid_power_kw: (number | null)[];
      battery_power_kw: (number | null)[];
      soc_percent: (number | null)[];
      residual_power_kw: (number | null)[];
      is_24h?: boolean;
      selected_date?: string;
    }>(`/datasets/${datasetId}/timeline${q}`);
  },
  getSolar: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/solar`),
  getConsumption: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/consumption`),
  getBattery: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/battery`),
  getGrid: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/grid`),
  getBalance: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/balance`),
  getEvents: (datasetId: string) => fetchJson<any[]>(`/datasets/${datasetId}/events`),
  getStatistics: (datasetId: string) => fetchJson<any>(`/datasets/${datasetId}/statistics`),
  getAnomalies: (datasetId: string) => fetchJson<any[]>(`/datasets/${datasetId}/anomalies`),
  runScenario: (datasetId: string, payload: { add_battery_kwh: number; add_pv_kwp: number; new_reserve_soc: number; shift_load_kwh: number }) => {
    return fetchJson<any>(`/datasets/${datasetId}/scenarios`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  getFinance: (datasetId: string, tariffType = "flat", flatRate?: number, systemCapex?: number) => {
    let url = `/datasets/${datasetId}/finance?tariff_type=${tariffType}`;
    if (flatRate !== undefined) url += `&flat_rate=${flatRate}`;
    if (systemCapex !== undefined) url += `&system_capex=${systemCapex}`;
    return fetchJson<any>(url);
  },
  getHistoricalDaily: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<DailySummaryItem[]>(`/historical/daily${q}`);
  },
  getHistoricalWeekly: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<any[]>(`/historical/weekly${q}`);
  },
  getHistoricalMonthly: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<any[]>(`/historical/monthly${q}`);
  },
  getHistoricalHourlyProfile: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<any[]>(`/historical/hourly_profile${q}`);
  },
  getHistoricalHeatmap: (metric: string = "pv_power_kw", datasetId?: string) => {
    let url = `/historical/heatmap?metric=${metric}`;
    if (datasetId) url += `&dataset_id=${encodeURIComponent(datasetId)}`;
    return fetchJson<{ dates: string[]; hours: string[]; matrix: any[] }>(url);
  },
  getHistoricalAverages: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<any>(`/historical/averages${q}`);
  },
  compareHistoricalPeriods: (dateAStart: string, dateAEnd: string, dateBStart: string, dateBEnd: string, datasetId?: string) => {
    let url = `/historical/compare?date_a_start=${dateAStart}&date_a_end=${dateAEnd}&date_b_start=${dateBStart}&date_b_end=${dateBEnd}`;
    if (datasetId) url += `&dataset_id=${encodeURIComponent(datasetId)}`;
    return fetchJson<any>(url);
  },
  getWeekdaysVsWeekends: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<{ hours_12h: string[]; weekday_hourly_load_kw: number[]; weekend_hourly_load_kw: number[]; weekday_sample_count: number; weekend_sample_count: number }>(`/historical/weekdays_vs_weekends${q}`);
  },
  generateReport: (datasetId: string, reportType: "pdf" | "xlsx" | "json") => {
    return fetchJson<{ report_id: string; filename: string; report_type: string; download_url: string }>(`/datasets/${datasetId}/reports/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_type: reportType })
    });
  },
  getDownloadUrl: (reportId: string) => `${API_BASE}/reports/${reportId}/download`,
  getBillingOverview: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<BillForecastResponse>(`/billing/overview${q}`);
  },
  getBillingProgress: (datasetId?: string) => {
    const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return fetchJson<BillingProgressResponse>(`/billing/progress${q}`);
  },
  getBillingStatement: (mode: "actual" | "expected" | "lower" | "higher" = "expected", datasetId?: string) => {
    let url = `/billing/statement?mode=${mode}`;
    if (datasetId) url += `&dataset_id=${encodeURIComponent(datasetId)}`;
    return fetchJson<StatementOfAccount>(url);
  },
  getBillingProfile: () => {
    return fetchJson<TEIBillingProfile>("/billing/profile");
  },
  updateBillingProfile: (profile: TEIBillingProfile) => {
    return fetchJson<{ status: string; profile: TEIBillingProfile }>("/billing/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile)
    });
  },
  getBillingRates: () => {
    return fetchJson<RateScheduleHistoryItem[]>("/billing/rates");
  },
  checkBillingRatesNow: () => {
    return fetchJson<{ status: string; message: string; checked_at: string; rate_change_alert: any; effective_month: string }>("/billing/rates/check_now", {
      method: "POST"
    });
  },
  addManualRateSchedule: (payload: { effective_month: string; customer_class?: string; generation_charge: number; generation_vat?: number; distribution_charge?: number; transmission_charge?: number; system_loss_charge?: number }) => {
    return fetchJson<{ status: string; schedule_id: string }>("/billing/rates/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  calculateRateSensitivity: (payload: { delta_gen_rate: number; delta_usage_pct: number; custom_kwh?: number }, datasetId?: string) => {
    let url = "/billing/sensitivity";
    if (datasetId) url += `?dataset_id=${encodeURIComponent(datasetId)}`;
    return fetchJson<RateSensitivityResponse>(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  getHistoricalBills: () => {
    return fetchJson<HistoricalBillRecord[]>("/billing/history");
  },
  addHistoricalBill: (bill: { billing_period_start: string; billing_period_end: string; billed_kwh: number; actual_amount_due: number; predicted_amount_due?: number; notes?: string }) => {
    return fetchJson<HistoricalBillRecord>("/billing/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bill)
    });
  },
  deleteHistoricalBill: (billId: string) => {
    return fetchJson<{ status: string; id: string }>(`/billing/history/${billId}`, {
      method: "DELETE"
    });
  },
  getDeyeStatus: () => {
    return fetchJson<DeyeStatusResponse>("/deye/status");
  },
  saveDeyeConfig: (payload: DeyeConfigPayload) => {
    return fetchJson<DeyeStatusResponse>("/deye/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  testDeyeConnection: (credentials?: DeyeConfigPayload) => {
    return fetchJson<{ success: boolean; message: string }>("/deye/test", {
      method: "POST",
      headers: credentials ? { "Content-Type": "application/json" } : undefined,
      body: credentials ? JSON.stringify(credentials) : undefined
    });
  },
  syncDeyeNow: (credentials?: DeyeConfigPayload) => {
    return fetchJson<{ status: string; message: string; records_fetched: number; records_inserted: number }>("/deye/sync", {
      method: "POST",
      headers: credentials ? { "Content-Type": "application/json" } : undefined,
      body: credentials ? JSON.stringify(credentials) : undefined
    });
  },
  syncDeyeRange: (startDate: string, endDate: string, credentials?: DeyeConfigPayload) => {
    return fetchJson<{ status: string; message: string; records_inserted: number; datasets_created?: string[]; days_count?: number; dataset_id?: string; filename?: string }>("/deye/sync_range", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date: startDate, end_date: endDate, credentials })
    });
  },
  getDeyeMissingDates: () => {
    return fetchJson<{ missing_dates: string[]; count: number }>("/deye/missing_dates");
  },
  syncDeyeMissing: () => {
    return fetchJson<{ status: string; message: string; records_inserted: number; backfilled_dates?: string[] }>("/deye/sync_missing", {
      method: "POST"
    });
  },
  getDeyeLiveFlow: () => {
    return fetchJson<LiveFlowResponse>("/deye/live_flow");
  },
  getDeyeHealth: () => {
    return fetchJson<StationHealthResponse>("/deye/health");
  },
  getWeatherIntelligence: () => {
    return fetchJson<WeatherIntelligenceResponse>("/weather/intelligence");
  },
  previewIngestionFile: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchJson<FilePreviewResponse>("/ingestion/preview", {
      method: "POST",
      body: formData
    });
  },
  getGridClassification: (datasetId: string) => {
    return fetchJson<any>(`/datasets/${datasetId}/grid_classification`);
  },
  simulateHardwareUpgrade: (datasetId: string, payload: { add_battery_kwh: number; add_pv_kwp: number; new_reserve_soc: number; shift_load_kwh: number }) => {
    return fetchJson<UpgradeSimulationResponse>(`/datasets/${datasetId}/simulation_upgrade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  getAnalystPresets: () => {
    return fetchJson<AnalystPresetQuery[]>("/analyst/presets");
  },
  queryAnalyst: (datasetId: string, queryKey: string, queryText?: string) => {
    return fetchJson<AnalystResponse>(`/datasets/${datasetId}/analyst/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_key: queryKey, query_text: queryText || "" })
    });
  },
  streamAnalystQuery: async (
    datasetId: string,
    queryText: string,
    onChunk: (data: any) => void,
    signal?: AbortSignal
  ) => {
    const res = await fetch(`${API_BASE}/datasets/${datasetId}/analyst/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_text: queryText }),
      signal
    });
    if (!res.ok) {
      throw new Error(`Streaming failed: HTTP ${res.status}`);
    }
    const reader = res.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            onChunk(data);
          } catch {}
        }
      }
    }
  },
  getAnalystPerformance: () => {
    return fetchJson<AnalystDiagnosticEngineStats>("/analyst/performance");
  },
  getAnalystMcpStatus: () => {
    return fetchJson<AnalystDiagnosticEngineStats>("/analyst/mcp/status");
  }
};

export interface TEIBillingProfile {
  customer_class: string;
  billing_cycle_day: number;
  cycle_start_date?: string;
  cycle_end_date?: string;
  prev_meter_reading?: number | null;
  latest_meter_reading?: number | null;
  meter_reading_date?: string | null;
  connection_type: string;
  is_lifeline_eligible: boolean;
  is_senior_eligible: boolean;
  is_prompt_payment_eligible: boolean;
  previous_unpaid_balance: number;
  payments_received: number;
  forecast_method: string;
  updated_at?: string;
}

export interface BillLineItem {
  component_id: string;
  name: string;
  category: string;
  rate_applied: number;
  rate_unit: string;
  billed_quantity: number;
  amount: number;
  vat_amount: number;
  total_with_vat: number;
  explanation: string;
  formula: string;
  vat_treatment: string;
}

export interface StatementOfAccount {
  billing_period_start: string;
  billing_period_end: string;
  customer_class: string;
  effective_rate_schedule_month: string;
  billed_kwh: number;
  generation_transmission_charges: number;
  distribution_charges: number;
  other_charges: number;
  subtotal_electricity_charges: number;
  government_taxes: number;
  discounts: number;
  net_metering_credits: number;
  total_current_charges: number;
  previous_unpaid_balance: number;
  payments_received: number;
  total_amount_due: number;
  line_items: BillLineItem[];
  effective_average_rate_per_kwh: number;
  is_estimate: boolean;
  disclaimer: string;
}

export interface BillForecastScenario {
  name: string;
  description: string;
  projected_additional_kwh: number;
  total_projected_kwh: number;
  estimated_current_charges: number;
  estimated_total_amount: number;
  daily_import_rate_kwh: number;
  statement: StatementOfAccount;
}

export interface BillForecastResponse {
  billing_cycle_start: string;
  billing_cycle_end: string;
  next_meter_reading_date: string;
  days_elapsed: number;
  days_remaining: number;
  cycle_total_days: number;
  actual_imported_kwh: number;
  actual_exported_kwh: number;
  active_rate_effective_month: string;
  active_generation_charge: number;
  active_generation_vat: number;
  last_rate_check_timestamp: string;
  rate_monitor_status: string;
  rate_change_alert?: {
    has_changed: boolean;
    previous_rate: number;
    new_rate: number;
    difference_per_kwh: number;
    effective_month: string;
    publication_date: string;
    summary: string;
  } | null;
  current_so_far_statement: StatementOfAccount;
  lower_estimate: BillForecastScenario;
  expected_estimate: BillForecastScenario;
  higher_estimate: BillForecastScenario;
  forecasting_method: string;
  data_coverage_percent: number;
  solar_savings: {
    bill_without_solar: number;
    bill_with_solar: number;
    savings_pesos: number;
    savings_percentage: number;
    avoided_grid_kwh: number;
    direct_solar_used_kwh: number;
    direct_solar_savings_pesos: number;
    battery_discharged_kwh: number;
    battery_savings_pesos: number;
    net_metering_credits_pesos: number;
    household_total_demand_kwh: number;
    actual_imported_kwh: number;
  };
}

export interface BillingProgressTimelineItem {
  date: string;
  day_label: string;
  is_actual: boolean;
  is_today: boolean;
  is_meter_reading: boolean;
  daily_kwh: number;
  cumulative_kwh_actual: number | null;
  cumulative_cost_actual: number | null;
  cumulative_kwh_expected: number;
  cumulative_cost_expected: number;
}

export interface BillingProgressResponse {
  start_date: string;
  end_date: string;
  today_date: string;
  average_daily_kwh: number;
  timeline: BillingProgressTimelineItem[];
}

export interface RateScheduleHistoryItem {
  id: string;
  effective_month: string;
  customer_class: string;
  publication_date: string;
  source_url: string;
  document_hash: string;
  verification_status: string;
  is_active: boolean;
  created_at: string;
  generation_charge: number;
  components_count: number;
}

export interface HistoricalBillRecord {
  id: string;
  billing_period_start: string;
  billing_period_end: string;
  billed_kwh: number;
  actual_amount_due: number;
  predicted_amount_due: number | null;
  variance_pesos: number | null;
  variance_percent: number | null;
  accuracy_percent: number | null;
  notes: string;
  created_at: string;
}

export interface RateSensitivityResponse {
  baseline_kwh: number;
  simulated_kwh: number;
  delta_gen_rate: number;
  delta_usage_pct: number;
  baseline_bill: number;
  simulated_bill: number;
  difference_pesos: number;
  difference_percentage: number;
  baseline_statement: StatementOfAccount;
  simulated_statement: StatementOfAccount;
}

export interface DeyeConfigPayload {
  station_id?: string;
  app_id?: string;
  app_secret?: string;
  username?: string;
  password?: string;
  auto_sync?: boolean;
  sync_interval_min?: number;
  reconciliation_policy?: string;
}

export interface DeyeStatusResponse {
  is_configured: boolean;
  has_app_secret?: boolean;
  has_password?: boolean;
  station_id: string;
  app_id: string;
  username?: string;
  auto_sync: boolean;
  sync_interval_min: number;
  last_sync_time: string | null;
  sync_status: string;
  sync_message: string;
  reconciliation_policy: string;
  device_hierarchy: {
    installation_name: string;
    station: { station_id: string; status: string };
    logger: { logger_serial: string; firmware_version: string; reporting_interval_min: number; status: string };
    inverter: { inverter_serial: string; model: string; rated_power_kw: number; status: string };
  };
  recent_logs: Array<{
    id: string;
    sync_time: string;
    records_fetched: number;
    records_inserted: number;
    status: string;
    error_message: string | null;
  }>;
}

export interface WeatherIntelligenceResponse {
  location: string;
  latitude: number;
  longitude: number;
  timezone: string;
  current_conditions: {
    cloud_cover_percent: number;
    solar_radiation_wm2: number;
    temperature_c: number;
  };
  tomorrow_forecast: {
    date: string;
    average_cloud_cover_percent: number;
    expected_solar_kwh: number;
    conservative_solar_kwh: number;
    optimistic_solar_kwh: number;
    probability_full_charge_percent: number;
    projected_sunset_soc_percent: number;
    projected_night_autonomy_hours: number;
    projected_night_autonomy_formatted: string;
  };
  hourly_forecast: Array<{
    time: string;
    hour: number;
    solar_radiation_wm2: number;
    cloud_cover_percent: number;
    temperature_c: number;
    estimated_pv_power_kw: number;
  }>;
}

export interface FilePreviewResponse {
  filename: string;
  file_format: string;
  filesize_bytes: number;
  file_hash: string;
  total_records: number;
  start_time: string | null;
  end_time: string | null;
  sampling_interval_min: number;
  columns_detected: Record<string, string>;
  is_duplicate: boolean;
  existing_dataset_id: string | null;
  quality_score: number;
  potential_issues: string[];
}

export interface UpgradeSimulationResponse {
  status: string;
  inputs: {
    baseline_battery_kwh: number;
    added_battery_kwh: number;
    baseline_pv_kwp: number;
    added_pv_kwp: number;
    new_reserve_soc: number;
    shifted_load_kwh: number;
    tariff_rate: number;
  };
  baseline: {
    daily_grid_import_kwh: number;
    daily_solar_yield_kwh: number;
    daily_household_load_kwh: number;
    span_days: number;
  };
  modeled_result: {
    modeled_daily_grid_kwh: number;
    daily_grid_reduction_kwh: number;
    grid_reduction_percentage: number;
    added_night_autonomy_hours: number;
    added_night_autonomy_formatted: string;
    daily_savings_php: number;
    monthly_savings_php: number;
    annual_savings_php: number;
    estimated_investment_cost_php: number;
    simple_payback_years: number;
    ten_year_npv_php: number;
  };
  electrical_limits: {
    inverter_rated_continuous_kw: number;
    inverter_peak_apparent_va: number;
    inverter_max_battery_current_a: number;
    bms_configured_limit_a: number;
    effective_battery_current_limit_a: number;
    max_battery_charge_power_kw: number;
    pv_mppt_operating_range_v: string;
    pv_max_voltage_v: string;
    daily_inverter_clipped_kwh: number;
    is_clipping_observed: boolean;
  };
  comparison_options: Array<{
    name: string;
    description: string;
    added_battery_kwh: number;
    added_pv_kwp: number;
    estimated_cost_php: number;
    daily_grid_reduction_kwh: number;
    monthly_savings_php: number;
    payback_years: number;
    ten_year_npv_php: number;
  }>;
}

export interface AnalystPresetQuery {
  id: string;
  category: string;
  question: string;
}

export interface AnalystResponse {
  query_key: string;
  title: string;
  what_happened: string;
  what_data_shows: string;
  why_it_happened: string;
  energy_or_money_impact: string;
  what_to_do: string;
  confidence_level: string;
}

export interface AnalystDiagnosticEngineStats {
  mcp_connected: boolean;
  mcp_endpoint: string;
  station_name: string;
  station_id: string;
  inverter_sn: string;
  read_only_enforced: boolean;
  inference_engine: string;
  hardware_profile: string;
  utility: string;
}

export interface LiveFlowResponse {
  success: boolean;
  station_name: string;
  station_id: string;
  inverter_model: string;
  inverter_serial: string;
  connection_status: string;
  is_on_grid: boolean;
  last_update_time: string;
  nodes: {
    solar: {
      power_w: number;
      power_kw: number;
      is_active: boolean;
    };
    battery: {
      soc_percent: number;
      power_w: number;
      power_kw: number;
      state: "CHARGING" | "DISCHARGING" | "IDLE";
      is_charging: boolean;
      is_discharging: boolean;
    };
    inverter: {
      status: string;
      throughput_w: number;
      throughput_kw: number;
    };
    grid: {
      power_w: number;
      power_kw: number;
      status_label: string;
      state: "IMPORT" | "EXPORT" | "IDLE";
      is_importing: boolean;
      is_exporting: boolean;
    };
    load: {
      power_w: number;
      power_kw: number;
      is_active: boolean;
    };
    ups: {
      power_w: number;
      power_kw: number;
      is_active: boolean;
    };
  };
  summary: {
    accumulative_production_kwh: number;
    accumulative_consumption_kwh: number;
    daily_production_kwh: number;
    weather_temp_c: number;
  };
  utilization?: {
    consumption_total_kwh: number;
    consumption_breakdown: Array<{
      label: string;
      kwh: number;
      pct: number;
      color: string;
    }>;
    production_total_kwh: number;
    production_breakdown: Array<{
      label: string;
      kwh: number;
      pct: number;
      color: string;
    }>;
  };
}

export interface StationHealthResponse {
  station_id: string;
  station_name: string;
  overall_status: string;
  is_healthy: boolean;
  mcp_endpoint: string;
  read_only_enforced: boolean;
  realtime_power: {
    pv_kw: number;
    load_kw: number;
    battery_kw: number;
    grid_kw: number;
    battery_soc_percent: number;
  };
  device_health: {
    logger: {
      serial: string;
      status: string;
      reporting_interval_min: number;
    };
    inverter: {
      serial: string;
      model: string;
      status: string;
      rated_output_kw: number;
    };
    battery: {
      model: string;
      soc_percent: number;
      status: string;
    };
  };
  alerts_count: number;
  active_alerts: any[];
  recommendation: string;
}
