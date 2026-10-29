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
  inverter_power_kw: number;
  battery_chemistry: string;
  battery_voltage: number;
  battery_capacity_kwh: number;
  usable_capacity_kwh: number;
  reserve_soc: number;
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
  getTimeline: (datasetId: string) => fetchJson<{
    timestamps: string[];
    timestamps_12h?: string[];
    pv_power_kw: number[];
    load_power_kw: number[];
    grid_power_kw: number[];
    battery_power_kw: number[];
    soc_percent: number[];
    residual_power_kw: number[];
  }>(`/datasets/${datasetId}/timeline`),
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
  getFinance: (datasetId: string, tariffType = "flat", flatRate?: number) => {
    let url = `/datasets/${datasetId}/finance?tariff_type=${tariffType}`;
    if (flatRate !== undefined) url += `&flat_rate=${flatRate}`;
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
  getDownloadUrl: (reportId: string) => `${API_BASE}/reports/${reportId}/download`
};
