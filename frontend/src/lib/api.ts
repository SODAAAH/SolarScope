const API_BASE = "/api";
const PROJECT_STORAGE_KEY = "solarscope_project_id";
const BILLING_PROFILE_STORAGE_KEY = "solarscope_billing_profile_v2";
const RATE_SCHEDULE_STORAGE_KEY = "solarscope_tei_rate_schedule_v1";
const LEGACY_DEYE_KEYS = [
  "solarscope_deye_token",
  "solarscope_deye_station_id",
  "solarscope_deye_mode",
];
let inMemoryCsrfToken = "";

export function getActiveProjectId(): string {
  try {
    return localStorage.getItem(PROJECT_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function clearUserClientCaches(preserveProject = true): void {
  clearApiCache();
  try {
    localStorage.removeItem("solarscope_dataset_id");
    localStorage.removeItem("solarscope_cached_live_flow_v3");
    localStorage.removeItem("solarscope_cached_live_flow_v2");
    localStorage.removeItem(BILLING_PROFILE_STORAGE_KEY);
    localStorage.removeItem(RATE_SCHEDULE_STORAGE_KEY);
    if (!preserveProject) {
      localStorage.removeItem(PROJECT_STORAGE_KEY);
    }
    sessionStorage.removeItem("solarscope_cached_live_flow");
    sessionStorage.removeItem("solarscope_cached_daily");
    const keysToRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      if (k && k.startsWith("solarscope_cached_summary_")) {
        keysToRemove.push(k);
      }
    }
    for (const k of keysToRemove) {
      sessionStorage.removeItem(k);
    }
  } catch {}
}

export function setActiveProjectId(projectId: string, emitEvent = true): void {
  const prev = getActiveProjectId();
  try {
    if (projectId) {
      localStorage.setItem(PROJECT_STORAGE_KEY, projectId);
    } else {
      localStorage.removeItem(PROJECT_STORAGE_KEY);
    }
  } catch {}
  if (prev !== projectId) {
    clearUserClientCaches(true);
    if (emitEvent) {
      dispatchAppEvent("solarscope:project-changed");
    }
  }
}

export function setCsrfToken(token?: string | null): void {
  if (token) {
    inMemoryCsrfToken = token;
  }
}

export function getCsrfToken(): string {
  try {
    if (typeof document !== "undefined" && document.cookie) {
      const parts = document.cookie.split(";");
      for (const part of parts) {
        const idx = part.indexOf("=");
        if (idx === -1) continue;
        const name = part.slice(0, idx).trim();
        if (name === "solarscope_csrf") {
          const val = decodeURIComponent(part.slice(idx + 1).trim());
          if (val) return val;
        }
      }
    }
  } catch {}
  return inMemoryCsrfToken;
}

function getScopedStorageKey(baseKey: string): string {
  const pid = getActiveProjectId() || "default";
  return `${baseKey}::${pid}`;
}

function clearLegacyDeyeStorage(): void {
  try {
    for (const k of LEGACY_DEYE_KEYS) {
      localStorage.removeItem(k);
    }
    localStorage.removeItem("solarscope_billing_profile");
    localStorage.removeItem("solarscope_cached_live_flow_v2");
    sessionStorage.removeItem("solarscope_cached_live_flow");
  } catch {}
}

export function getStoredBillingProfile(): TEIBillingProfile | null {
  try {
    const raw = localStorage.getItem(getScopedStorageKey(BILLING_PROFILE_STORAGE_KEY));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function setStoredBillingProfile(profile: TEIBillingProfile): void {
  try {
    localStorage.setItem(getScopedStorageKey(BILLING_PROFILE_STORAGE_KEY), JSON.stringify(profile));
  } catch {}
}

export function getStoredRateSchedule(): any | null {
  try {
    const raw = localStorage.getItem(getScopedStorageKey(RATE_SCHEDULE_STORAGE_KEY));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function setStoredRateSchedule(schedule: any): void {
  try {
    if (schedule && typeof schedule === "object") {
      localStorage.setItem(getScopedStorageKey(RATE_SCHEDULE_STORAGE_KEY), JSON.stringify(schedule));
    }
  } catch {}
}

function buildBillingHeaders(extra?: Record<string, string>): Record<string, string> {
  return { ...(extra || {}) };
}

function buildRequestHeaders(method: string, extra?: HeadersInit): Headers {
  const headers = new Headers(extra || {});
  const projectId = getActiveProjectId();
  if (projectId && !headers.has("X-Project-Id")) {
    headers.set("X-Project-Id", projectId);
  }
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const csrf = getCsrfToken();
    if (csrf && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", csrf);
    }
  }
  return headers;
}

export function persistDeyeSession(): void {
  clearLegacyDeyeStorage();
}

function dispatchAppEvent(name: string): void {
  clearApiCache();
  try {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(name));
    }
  } catch {}
}

const GET_CACHE_TTL_MS = 30000;
const apiGetCache = new Map<string, { expiresAt: number; data: any }>();
const inflightGetRequests = new Map<string, Promise<any>>();

export function clearApiCache(): void {
  apiGetCache.clear();
  inflightGetRequests.clear();
}

function isCacheableGet(endpoint: string, options?: RequestInit): boolean {
  const method = (options?.method || "GET").toUpperCase();
  if (method !== "GET") return false;
  if (endpoint.includes("/deye/live_flow") || endpoint.includes("/health") || endpoint.includes("/auth/")) return false;
  if (endpoint.includes("fresh=true") || endpoint.includes("refresh=true")) return false;
  return true;
}

export async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const method = (options?.method || "GET").toUpperCase();
  if (method !== "GET") {
    clearApiCache();
  }

  const projectScope = getActiveProjectId() || "default";
  const cacheKey = `${projectScope}::${endpoint}`;
  const cacheable = isCacheableGet(endpoint, options);
  const now = Date.now();
  if (cacheable) {
    const cached = apiGetCache.get(cacheKey);
    if (cached && cached.expiresAt > now) {
      return cached.data as T;
    }
    const inflight = inflightGetRequests.get(cacheKey);
    if (inflight) {
      return inflight as Promise<T>;
    }
  }

  const url = `${API_BASE}${endpoint}`;
  const reqPromise = (async () => {
    try {
      const headers = buildRequestHeaders(method, options?.headers);
      const res = await fetch(url, {
        cache: "no-store",
        credentials: "include",
        ...options,
        headers,
      });
      if (!res.ok) {
        const errorText = await res.text();
        if (res.status === 401 && !endpoint.startsWith("/auth/")) {
          dispatchAppEvent("solarscope:auth-required");
        }
        throw new Error(`API Error [${res.status}]: ${errorText}`);
      }
      const data = await res.json();
      if (cacheable) {
        apiGetCache.set(cacheKey, { expiresAt: Date.now() + GET_CACHE_TTL_MS, data });
      }
      return data as T;
    } catch (err: any) {
      if (err.name === "TypeError" && (err.message.includes("fetch") || err.message.includes("network") || err.message.includes("Failed"))) {
        throw new Error("Cannot reach SolarScope API server. Please ensure the backend service is running.");
      }
      throw err;
    } finally {
      if (cacheable) {
        inflightGetRequests.delete(cacheKey);
      }
    }
  })();

  if (cacheable) {
    inflightGetRequests.set(cacheKey, reqPromise);
  }
  return reqPromise;
}

export interface SystemSettings {
  station_name?: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
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
  updateSettings: async (data: SystemSettings) => {
    const res = await fetchJson<{ status: string; settings: SystemSettings }>("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    dispatchAppEvent("solarscope:settings-updated");
    return res;
  },
  uploadDataset: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetchJson<{ dataset_id: string; filename: string; file_hash?: string; is_duplicate?: boolean; duplicate_of?: string; available_sheets: string[]; selected_sheet: string | null }>("/datasets/upload", {
      method: "POST",
      body: formData,
    });
    dispatchAppEvent("solarscope:sources-updated");
    return res;
  },
  uploadDatasetsBatch: async (files: File[]) => {
    const formData = new FormData();
    files.forEach(f => formData.append("files", f));
    const res = await fetchJson<{ total_uploaded: number; files: any[] }>("/datasets/upload_batch", {
      method: "POST",
      body: formData,
    });
    dispatchAppEvent("solarscope:sources-updated");
    return res;
  },
  listSources: () => fetchJson<SourceItem[]>("/sources"),
  updateSource: async (sourceId: string, payload: { is_included?: boolean; sheet_name?: string }) => {
    const res = await fetchJson<{ status: string; source_id: string }>(`/sources/${sourceId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    dispatchAppEvent("solarscope:sources-updated");
    return res;
  },
  deleteSource: async (sourceId: string) => {
    const res = await fetchJson<{ status: string; source_id: string }>(`/sources/${sourceId}`, {
      method: "DELETE"
    });
    dispatchAppEvent("solarscope:sources-updated");
    return res;
  },
  autoCommitDataset: async (datasetId: string) => {
    const res = await fetchJson<{
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
    dispatchAppEvent("solarscope:sources-updated");
    return res;
  },
  autoCommitAllDatasets: async () => {
    const res = await fetchJson<{ total_processed: number; committed: any[] }>("/datasets/auto_commit_all", {
      method: "POST"
    });
    dispatchAppEvent("solarscope:sources-updated");
    return res;
  },
  getPreview: (datasetId: string, sheetName?: string) => {
    const q = sheetName ? `?sheet_name=${encodeURIComponent(sheetName)}` : "";
    return fetchJson<DatasetPreview>(`/datasets/${datasetId}/preview${q}`);
  },
  commitDataset: async (datasetId: string, mappings: Record<string, string>, signConventions: Record<string, string>, selectedSheet: string) => {
    const res = await fetchJson<{ status: string; dataset_id: string; total_records: number; quality_score: number; quality_status: string; start_time_12h?: string; end_time_12h?: string }>(`/datasets/${datasetId}/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        selected_sheet: selectedSheet,
        mappings,
        sign_conventions: signConventions
      }),
    });
    dispatchAppEvent("solarscope:sources-updated");
    return res;
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
  getBillingOverview: (datasetId?: string, fresh?: boolean) => {
    const params = new URLSearchParams();
    if (datasetId) params.set("dataset_id", datasetId);
    if (fresh) params.set("fresh", "true");
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchJson<BillForecastResponse>(`/billing/overview${q}`, { headers: buildBillingHeaders() });
  },
  getBillingProgress: (datasetId?: string, fresh?: boolean) => {
    const params = new URLSearchParams();
    if (datasetId) params.set("dataset_id", datasetId);
    if (fresh) params.set("fresh", "true");
    const q = params.toString() ? `?${params.toString()}` : "";
    return fetchJson<BillingProgressResponse>(`/billing/progress${q}`, { headers: buildBillingHeaders() });
  },
  getBillingStatement: (mode: "actual" | "expected" | "lower" | "higher" = "expected", datasetId?: string) => {
    let url = `/billing/statement?mode=${mode}`;
    if (datasetId) url += `&dataset_id=${encodeURIComponent(datasetId)}`;
    return fetchJson<StatementOfAccount>(url, { headers: buildBillingHeaders() });
  },
  getBillingProfile: async (fresh?: boolean) => {
    const q = fresh ? "?fresh=true" : "";
    const prof = await fetchJson<TEIBillingProfile>(`/billing/profile${q}`, { headers: buildBillingHeaders() });
    if (prof) {
      setStoredBillingProfile(prof);
    }
    return prof;
  },
  updateBillingProfile: async (profile: TEIBillingProfile) => {
    const res = await fetchJson<{ status: string; profile: TEIBillingProfile }>("/billing/profile", {
      method: "PUT",
      headers: buildBillingHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(profile)
    });
    if (res && res.profile) {
      setStoredBillingProfile(res.profile);
    } else {
      setStoredBillingProfile(profile);
    }
    return res;
  },
  getBillingRates: (fresh?: boolean) => {
    const q = fresh ? "?fresh=true" : "";
    return fetchJson<RateScheduleHistoryItem[]>(`/billing/rates${q}`);
  },
  checkBillingRatesNow: async () => {
    const res = await fetchJson<{
      status: string;
      message: string;
      checked_at: string;
      rate_change_alert: any;
      effective_month: string;
      active_schedule?: any;
      rates?: RateScheduleHistoryItem[];
      forecast?: BillForecastResponse;
      progress?: BillingProgressResponse;
    }>("/billing/rates/check_now", {
      method: "POST",
      headers: buildBillingHeaders()
    });
    if (res?.active_schedule) {
      setStoredRateSchedule(res.active_schedule);
    }
    return res;
  },
  addManualRateSchedule: async (payload: { effective_month: string; customer_class?: string; generation_charge: number; generation_vat?: number; distribution_charge?: number; transmission_charge?: number; system_loss_charge?: number }) => {
    const res = await fetchJson<{ status: string; schedule_id: string; active_schedule?: any }>("/billing/rates/manual", {
      method: "POST",
      headers: buildBillingHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    if (res?.active_schedule) {
      setStoredRateSchedule(res.active_schedule);
    }
    return res;
  },
  activateBillingRate: async (scheduleId: string) => {
    const res = await fetchJson<{ status: string; schedule_id: string; active_schedule?: any }>(`/billing/rates/${encodeURIComponent(scheduleId)}/activate`, {
      method: "POST",
      headers: buildBillingHeaders()
    });
    if (res?.active_schedule) {
      setStoredRateSchedule(res.active_schedule);
    }
    return res;
  },
  calculateRateSensitivity: (payload: { delta_gen_rate: number; delta_usage_pct: number; custom_kwh?: number }, datasetId?: string) => {
    let url = "/billing/sensitivity";
    if (datasetId) url += `?dataset_id=${encodeURIComponent(datasetId)}`;
    return fetchJson<RateSensitivityResponse>(url, {
      method: "POST",
      headers: buildBillingHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
  },
  getMonthlyEstimates: (fresh?: boolean) => {
    const q = fresh ? "?fresh=true" : "";
    return fetchJson<MonthlyEstimateRecord[]>(`/billing/estimates${q}`, { headers: buildBillingHeaders() });
  },
  deleteMonthlyEstimate: (estimateId: string) => {
    return fetchJson<{ status: string; id: string }>(`/billing/estimates/${encodeURIComponent(estimateId)}`, {
      method: "DELETE"
    });
  },
  getHistoricalBills: (fresh?: boolean) => {
    const q = fresh ? "?fresh=true" : "";
    return fetchJson<HistoricalBillRecord[]>(`/billing/history${q}`);
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
    clearLegacyDeyeStorage();
    return fetchJson<DeyeStatusResponse>("/deye/status");
  },
  saveDeyeConfig: async (payload: DeyeConfigPayload) => {
    const res = await fetchJson<DeyeStatusResponse>("/deye/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    clearLegacyDeyeStorage();
    try {
      localStorage.removeItem("solarscope_cached_live_flow_v3");
    } catch {}
    dispatchAppEvent("solarscope:deye-updated");
    return res;
  },
  clearDeyeConfig: async () => {
    const res = await fetchJson<DeyeStatusResponse>("/deye/config", {
      method: "DELETE"
    });
    clearLegacyDeyeStorage();
    try {
      localStorage.removeItem("solarscope_cached_live_flow_v3");
    } catch {}
    dispatchAppEvent("solarscope:deye-updated");
    return res;
  },
  testDeyeConnection: async (credentials?: DeyeConfigPayload) => {
    const res = await fetchJson<{ success: boolean; message: string; station_id?: string; is_demo?: boolean }>("/deye/test", {
      method: "POST",
      headers: credentials ? { "Content-Type": "application/json" } : undefined,
      body: credentials ? JSON.stringify(credentials) : undefined
    });
    if (res.success) {
      clearLegacyDeyeStorage();
      try {
        localStorage.removeItem("solarscope_cached_live_flow_v3");
      } catch {}
      dispatchAppEvent("solarscope:deye-updated");
    }
    return res;
  },
  syncDeyeNow: async (credentials?: DeyeConfigPayload) => {
    const res = await fetchJson<{ status: string; message: string; records_fetched: number; records_inserted: number; station_id?: string; is_demo?: boolean }>("/deye/sync", {
      method: "POST",
      headers: credentials ? { "Content-Type": "application/json" } : undefined,
      body: credentials ? JSON.stringify(credentials) : undefined
    });
    dispatchAppEvent("solarscope:sources-updated");
    dispatchAppEvent("solarscope:deye-updated");
    return res;
  },
  syncDeyeRange: async (startDate: string, endDate: string, credentials?: DeyeConfigPayload) => {
    const res = await fetchJson<{ status: string; message: string; records_inserted: number; datasets_created?: string[]; days_count?: number; dataset_id?: string; filename?: string; station_id?: string; is_demo?: boolean }>("/deye/sync_range", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start_date: startDate, end_date: endDate, credentials })
    });
    dispatchAppEvent("solarscope:sources-updated");
    dispatchAppEvent("solarscope:deye-updated");
    return res;
  },
  getDeyeMissingDates: () => {
    return fetchJson<{ missing_dates: string[]; count: number }>("/deye/missing_dates");
  },
  syncDeyeMissing: async () => {
    const res = await fetchJson<{ status: string; message: string; records_inserted: number; backfilled_dates?: string[] }>("/deye/sync_missing", {
      method: "POST"
    });
    dispatchAppEvent("solarscope:sources-updated");
    dispatchAppEvent("solarscope:deye-updated");
    return res;
  },
  getDeyeLiveFlow: async () => {
    clearLegacyDeyeStorage();
    return fetchJson<LiveFlowResponse>("/deye/live_flow");
  },
  getDeyeHealth: () => {
    clearLegacyDeyeStorage();
    return fetchJson<StationHealthResponse>("/deye/health");
  },
  getWeatherIntelligence: (refresh?: boolean) => {
    const q = refresh ? "?refresh=true" : "";
    return fetchJson<WeatherIntelligenceResponse>(`/weather/intelligence${q}`);
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
      credentials: "include",
      headers: buildRequestHeaders("POST", { "Content-Type": "application/json" }),
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
  },
  getAuthMe: async () => {
    const res = await fetchJson<AuthMeResponse>("/auth/me");
    if (res?.csrf_token) {
      setCsrfToken(res.csrf_token);
    }
    if (res?.active_project_id && !getActiveProjectId()) {
      setActiveProjectId(res.active_project_id, false);
    }
    return res;
  },
  login: async (payload: { email: string; password: string }) => {
    const res = await fetchJson<AuthMeResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res?.csrf_token) setCsrfToken(res.csrf_token);
    if (res?.active_project_id) setActiveProjectId(res.active_project_id, false);
    clearUserClientCaches(true);
    return res;
  },
  demoLogin: async () => {
    const res = await fetchJson<AuthMeResponse>("/auth/demo", {
      method: "POST"
    });
    if (res?.csrf_token) setCsrfToken(res.csrf_token);
    if (res?.active_project_id) setActiveProjectId(res.active_project_id, false);
    clearUserClientCaches(true);
    return res;
  },
  register: async (payload: { email: string; password: string; display_name?: string; installation_name?: string }) => {
    const res = await fetchJson<AuthMeResponse>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res?.csrf_token) setCsrfToken(res.csrf_token);
    if (res?.active_project_id) setActiveProjectId(res.active_project_id, false);
    clearUserClientCaches(true);
    return res;
  },
  logout: async () => {
    const res = await fetchJson<{ status: string }>("/auth/logout", {
      method: "POST"
    });
    inMemoryCsrfToken = "";
    clearUserClientCaches(false);
    dispatchAppEvent("solarscope:auth-changed");
    return res;
  },
  listProjects: () => fetchJson<{ active_project_id: string; projects: ProjectSummary[] }>("/projects"),
  createProject: async (payload: { name: string; description?: string; installation_type?: string }) => {
    const res = await fetchJson<{ status: string; project: ProjectSummary }>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res?.project?.id) {
      setActiveProjectId(res.project.id, true);
    }
    return res;
  },
  updateProject: (projectId: string, payload: { name?: string; description?: string; installation_type?: string }) => {
    return fetchJson<{ status: string; project: ProjectSummary }>(`/projects/${encodeURIComponent(projectId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  deleteProject: async (projectId: string) => {
    const res = await fetchJson<{ status: string; deleted_project_id?: string }>(`/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE"
    });
    clearUserClientCaches(false);
    dispatchAppEvent("solarscope:project-changed");
    return res;
  }
};

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description?: string;
  installation_type?: string;
  is_default?: number;
  owner_user_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthMeResponse {
  authenticated: boolean;
  auth_required?: boolean;
  hosted_mode?: boolean;
  is_local_mode?: boolean;
  user: AuthUser | null;
  projects: ProjectSummary[];
  active_project_id: string | null;
  csrf_token?: string;
}

export interface TEIBillingProfile {
  customer_class: string;
  billing_cycle_day: number;
  billing_month?: string | null;
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
  calculation_basis?: string | Record<string, any>;
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
  calculation_basis?: string | {
    is_estimate?: boolean;
    import_energy_basis?: string;
    telemetry_imported_kwh?: number;
    projected_exported_kwh?: number;
    rate_schedule_verification?: string;
    rate_effective_month?: string;
    customer_class?: string;
    connection_type?: string;
    forecast_sample_days?: number;
    cycle_days_observed?: number;
    solar_savings_attribution?: string;
  };
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

export interface MonthlyEstimateRecord {
  id: string;
  billing_month: string;
  billing_cycle_start: string;
  billing_cycle_end: string;
  customer_class: string;
  rate_effective_month: string;
  generation_charge: number;
  actual_imported_kwh: number;
  projected_kwh: number;
  lower_estimate_amount: number;
  expected_estimate_amount: number;
  higher_estimate_amount: number;
  solar_savings_pesos: number;
  savings_percentage: number;
  effective_average_rate: number;
  is_completed_cycle: boolean;
  updated_at: string;
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
  data_center?: string;
  auto_sync?: boolean;
  sync_interval_min?: number;
  reconciliation_policy?: string;
}

export interface DeyeStatusResponse {
  is_configured: boolean;
  is_demo?: boolean;
  has_app_secret?: boolean;
  has_password?: boolean;
  station_id: string;
  app_id: string;
  username?: string;
  data_center?: string;
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

export interface WeatherHourlyForecastItem {
  time: string;
  date?: string;
  hour: number;
  is_today?: boolean;
  is_now?: boolean;
  solar_radiation_wm2: number;
  cloud_cover_percent: number;
  temperature_c: number;
  precipitation_mm?: number;
  weather_code?: number | null;
  condition_label?: string;
  icon_key?: string;
  estimated_pv_power_kw: number;
}

export interface WeatherIntelligenceResponse {
  configured?: boolean;
  status?: string;
  message?: string;
  is_stale_fallback?: boolean;
  freshness_minutes?: number | null;
  forecast_basis?: string;
  location: string;
  latitude: number;
  longitude: number;
  timezone: string;
  fetched_at?: string | null;
  current_conditions: {
    cloud_cover_percent: number;
    solar_radiation_wm2: number;
    temperature_c: number;
    precipitation_mm?: number;
    wind_speed_kmh?: number;
    weather_code?: number | null;
    condition_label?: string;
    icon_key?: string;
    is_day?: boolean;
    observed_at?: string;
  } | null;
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
  } | null;
  hourly_forecast: WeatherHourlyForecastItem[];
  live_hourly_forecast?: WeatherHourlyForecastItem[];
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
  is_live?: boolean;
  data_source?: "live" | "demo" | "cached" | "offline";
  error?: string | null;
  token_expired?: boolean;
  freshness_minutes?: number | null;
  is_stale?: boolean;
  missing_fields?: string[];
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
    weather_temp_c: number | null;
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
