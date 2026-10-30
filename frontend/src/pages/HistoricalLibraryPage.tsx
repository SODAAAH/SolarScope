import React, { useEffect, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import {
  UploadCloud,
  Trash2,
  RefreshCw,
  CheckCircle2,
  Play,
  AlertCircle,
  Loader2,
  Database,
  Cloud,
  FileSearch,
  Check,
  AlertTriangle,
  Radio,
  ArrowRight,
  Wifi,
  Key
} from "lucide-react";
import {
  api,
  type SourceItem,
  type DeyeStatusResponse,
  type FilePreviewResponse
} from "../lib/api";
import { format12HourDateTime } from "../lib/formatters";
import { ConfirmModal } from "../components/ui/ConfirmModal";

interface OutletContextType {
  activeDatasetId: string | null;
  setActiveDatasetId: (id: string) => void;
}

interface IngestionProgress {
  total: number;
  current: number;
  currentFileName: string;
  percent: number;
  estimatedRemainingSec: number | null;
  elapsedSec: number;
}

export const HistoricalLibraryPage: React.FC = () => {
  const { activeDatasetId, setActiveDatasetId } = useOutletContext<OutletContextType>();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = searchParams.get("tab") || "datasets";

  const [sources, setSources] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [committingAll, setCommittingAll] = useState(false);
  const [committingId, setCommittingId] = useState<string | null>(null);
  const [progress, setProgress] = useState<IngestionProgress | null>(null);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filterTab, setFilterTab] = useState<"all" | "included" | "excluded" | "pending">("all");
  const [deleteTarget, setDeleteTarget] = useState<SourceItem | null>(null);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [deyeStatus, setDeyeStatus] = useState<DeyeStatusResponse | null>(null);
  const [deyeLoading, setDeyeLoading] = useState(false);
  const [deyeTesting, setDeyeTesting] = useState(false);
  const [deyeSyncing, setDeyeSyncing] = useState(false);
  const [deyeMessage, setDeyeMessage] = useState<string | null>(null);

  const [configStationId, setConfigStationId] = useState("");
  const [configAppId, setConfigAppId] = useState("");
  const [configAppSecret, setConfigAppSecret] = useState("");
  const [configUsername, setConfigUsername] = useState("");
  const [configPassword, setConfigPassword] = useState("");
  const [configAutoSync, setConfigAutoSync] = useState(false);
  const [configInterval, setConfigInterval] = useState(5);
  const [savingConfig, setSavingConfig] = useState(false);

  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const [previewResult, setPreviewResult] = useState<FilePreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const setTab = (tab: string) => {
    setSearchParams({ tab });
  };

  const fetchSources = async () => {
    setLoading(true);
    try {
      const data = await api.listSources();
      setSources(data);
    } catch (err: any) {
      setUploadStatus(`Error fetching sources: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchDeyeStatus = async () => {
    setDeyeLoading(true);
    try {
      const data = await api.getDeyeStatus();
      setDeyeStatus(data);
      if (data) {
        setConfigStationId(data.station_id || "62805884");
        setConfigAppId(data.app_id || "");
        setConfigUsername(data.username || "dy_YyWnmwcU");
        setConfigAutoSync(data.auto_sync || false);
        setConfigInterval(data.sync_interval_min || 5);
      }
    } catch (err: any) {
      setDeyeMessage(`Cloud status check: ${err.message}`);
    } finally {
      setDeyeLoading(false);
    }
  };

  const handleSaveDeyeConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingConfig(true);
    try {
      const res = await api.saveDeyeConfig({
        station_id: configStationId,
        app_id: configAppId,
        app_secret: configAppSecret,
        username: configUsername,
        password: configPassword,
        auto_sync: configAutoSync,
        sync_interval_min: configInterval
      });
      setDeyeStatus(res);
      setDeyeMessage("Deye Cloud credentials saved successfully.");
    } catch (err: any) {
      setDeyeMessage(`Failed to save credentials: ${err.message}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const handleApplyDemoConfig = async () => {
    setConfigStationId("STATION-2026");
    setConfigAppId("demo");
    setConfigAppSecret("demo_secret");
    setConfigUsername("demo@solarscope.local");
    setSavingConfig(true);
    try {
      const res = await api.saveDeyeConfig({
        station_id: "STATION-2026",
        app_id: "demo",
        app_secret: "demo_secret",
        username: "demo@solarscope.local",
        password: "",
        auto_sync: false,
        sync_interval_min: 5
      });
      setDeyeStatus(res);
      setDeyeMessage("Demo mode applied: Simulated live Deye Cloud connection enabled.");
    } catch (err: any) {
      setDeyeMessage(`Failed to apply demo: ${err.message}`);
    } finally {
      setSavingConfig(false);
    }
  };

  useEffect(() => {
    fetchSources();
    fetchDeyeStatus();
  }, []);

  const handleTestDeyeConnection = async () => {
    setDeyeTesting(true);
    setDeyeMessage(null);
    try {
      const res = await api.testDeyeConnection();
      setDeyeMessage(res.message);
      await fetchDeyeStatus();
    } catch (err: any) {
      setDeyeMessage(`Connection test: ${err.message}`);
    } finally {
      setDeyeTesting(false);
    }
  };

  const handleSyncDeyeNow = async () => {
    setDeyeSyncing(true);
    setDeyeMessage(null);
    try {
      const res = await api.syncDeyeNow();
      setDeyeMessage(`Sync result: ${res.message} (${res.records_inserted} rows inserted)`);
      await fetchDeyeStatus();
      await fetchSources();
    } catch (err: any) {
      setDeyeMessage(`Sync failed: ${err.message}`);
    } finally {
      setDeyeSyncing(false);
    }
  };

  const handleInspectPreview = async (file: File) => {
    setPreviewFile(file);
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewResult(null);
    try {
      const res = await api.previewIngestionFile(file);
      setPreviewResult(res);
    } catch (err: any) {
      setPreviewError(err.message || "Failed to inspect file.");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleCommitPreviewedFile = async () => {
    if (!previewFile) return;
    setUploading(true);
    try {
      const res = await api.uploadDatasetsBatch([previewFile]);
      if (res.files && res.files.length > 0 && res.files[0].dataset_id) {
        setActiveDatasetId(res.files[0].dataset_id);
      }
      setTab("datasets");
      await fetchSources();
    } catch (err: any) {
      setPreviewError(err.message || "Failed to commit inspected file.");
    } finally {
      setUploading(false);
    }
  };

  const processFileList = async (files: File[]) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadStatus(null);
    const total = files.length;
    const startTime = Date.now();
    let committedCount = 0;

    for (let i = 0; i < total; i++) {
      const file = files[i];
      const elapsed = (Date.now() - startTime) / 1000;
      const avgPerFile = i > 0 ? elapsed / i : 2.5;
      const remaining = Math.max(1, Math.round(avgPerFile * (total - i)));

      setProgress({
        total,
        current: i + 1,
        currentFileName: file.name,
        percent: Math.max(5, Math.round(((i + 0.2) / total) * 100)),
        estimatedRemainingSec: remaining,
        elapsedSec: Math.round(elapsed),
      });

      try {
        const res = await api.uploadDatasetsBatch([file]);
        if (res.files && res.files.length > 0) {
          committedCount++;
          if (i === 0 && res.files[0].dataset_id) {
            setActiveDatasetId(res.files[0].dataset_id);
          }
        }
        setProgress(prev => prev ? {
          ...prev,
          percent: Math.round(((i + 1) / total) * 100)
        } : null);
        await fetchSources();
      } catch (err: any) {
        setUploadStatus(`Error on ${file.name}: ${err.message}`);
        break;
      }
    }

    const totalElapsed = Math.max(1, Math.round((Date.now() - startTime) / 1000));
    setProgress({
      total,
      current: total,
      currentFileName: files[total - 1].name,
      percent: 100,
      estimatedRemainingSec: 0,
      elapsedSec: totalElapsed,
    });

    setTimeout(() => {
      setProgress(null);
      setUploading(false);
      setUploadStatus(`Processed and committed ${committedCount} of ${total} file(s) in ${totalElapsed}s.`);
    }, 700);
  };

  const handleAutoCommitAll = async () => {
    if (pendingSources.length === 0) return;
    setCommittingAll(true);
    setUploadStatus(null);
    const total = pendingSources.length;
    const startTime = Date.now();
    let committedCount = 0;

    for (let i = 0; i < total; i++) {
      const src = pendingSources[i];
      const elapsed = (Date.now() - startTime) / 1000;
      const avgPerFile = i > 0 ? elapsed / i : 1.8;
      const remaining = Math.max(1, Math.round(avgPerFile * (total - i)));

      setProgress({
        total,
        current: i + 1,
        currentFileName: src.filename,
        percent: Math.max(5, Math.round(((i + 0.2) / total) * 100)),
        estimatedRemainingSec: remaining,
        elapsedSec: Math.round(elapsed),
      });

      try {
        await api.autoCommitDataset(src.id);
        committedCount++;
        setProgress(prev => prev ? {
          ...prev,
          percent: Math.round(((i + 1) / total) * 100)
        } : null);
        await fetchSources();
      } catch (err: any) {
        setUploadStatus(`Error committing ${src.filename}: ${err.message}`);
        break;
      }
    }

    setProgress(null);
    setCommittingAll(false);
    setUploadStatus(`Committed ${committedCount} of ${total} pending file(s).`);
    await fetchSources();
  };

  const handleAutoCommitSingle = async (sourceId: string) => {
    setCommittingId(sourceId);
    try {
      await api.autoCommitDataset(sourceId);
      await fetchSources();
    } catch (err: any) {
      setUploadStatus(`Failed to commit dataset: ${err.message}`);
    } finally {
      setCommittingId(null);
    }
  };

  const handleToggleInclude = async (sourceId: string, currentVal: number) => {
    try {
      await api.updateSource(sourceId, { is_included: currentVal !== 1 });
      setSources(prev => prev.map(s => s.id === sourceId ? { ...s, is_included: currentVal === 1 ? 0 : 1 } : s));
    } catch (err: any) {
      setUploadStatus(`Failed to toggle inclusion: ${err.message}`);
    }
  };

  const handleConfirmSingleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteSource(deleteTarget.id);
      setSources(prev => prev.filter(s => s.id !== deleteTarget.id));
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(deleteTarget.id);
        return next;
      });
      if (activeDatasetId === deleteTarget.id) {
        setActiveDatasetId("");
      }
      setUploadStatus(`Removed ${deleteTarget.filename} from library.`);
      setDeleteTarget(null);
    } catch (err: any) {
      setUploadStatus(`Failed to remove ${deleteTarget.filename}: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const handleConfirmBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    const ids = Array.from(selectedIds);
    let deletedCount = 0;
    try {
      for (const id of ids) {
        await api.deleteSource(id);
        deletedCount++;
        if (activeDatasetId === id) {
          setActiveDatasetId("");
        }
      }
      setSources(prev => prev.filter(s => !selectedIds.has(s.id)));
      setSelectedIds(new Set());
      setIsBulkDeleting(false);
      setUploadStatus(`Successfully removed ${deletedCount} dataset(s) from historical library.`);
    } catch (err: any) {
      setUploadStatus(`Failed to delete selected datasets: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const handleBulkInclude = async (include: boolean) => {
    if (selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    try {
      for (const id of ids) {
        await api.updateSource(id, { is_included: include });
      }
      setSources(prev => prev.map(s => selectedIds.has(s.id) ? { ...s, is_included: include ? 1 : 0 } : s));
      setUploadStatus(`Updated ${ids.length} dataset(s) to ${include ? "included" : "excluded"}.`);
    } catch (err: any) {
      setUploadStatus(`Update failed: ${err.message}`);
    }
  };

  const totalRecords = sources.reduce((acc, s) => acc + (s.total_rows || 0), 0);
  const includedSources = sources.filter(s => s.is_included === 1);
  const pendingSources = sources.filter(s => (s.total_rows === 0 || !s.start_time));
  const excludedSources = sources.filter(s => s.is_included !== 1);

  const sortedSources = [...sources].sort((a, b) => {
    const dateA = a.start_time ? a.start_time.slice(0, 10) : a.filename;
    const dateB = b.start_time ? b.start_time.slice(0, 10) : b.filename;
    return dateA.localeCompare(dateB);
  });

  const filteredSources = sortedSources.filter(s => {
    if (filterTab === "included") return s.is_included === 1 && s.total_rows > 0;
    if (filterTab === "excluded") return s.is_included !== 1;
    if (filterTab === "pending") return s.total_rows === 0 || !s.start_time;
    return true;
  });

  const allFilteredSelected = filteredSources.length > 0 && filteredSources.every(s => selectedIds.has(s.id));

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Data Library & Ingestion Center
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Historical datasets, automatic Deye Cloud synchronization, and pre-import signal verification.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pendingSources.length > 0 && currentTab === "datasets" && (
            <button
              onClick={handleAutoCommitAll}
              disabled={committingAll || uploading}
              className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-50"
            >
              {committingAll ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Committing ({progress?.current || 1}/{pendingSources.length})</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Commit All Pending ({pendingSources.length})</span>
                </>
              )}
            </button>
          )}
          <button
            onClick={() => {
              fetchSources();
              fetchDeyeStatus();
            }}
            disabled={loading || deyeLoading}
            className="px-3 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading || deyeLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-8">
        <button
          onClick={() => setTab("datasets")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors ${
            currentTab === "datasets"
              ? "border-amber-600 text-amber-600 dark:text-amber-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Historical Datasets ({sources.length})</span>
        </button>
        <button
          onClick={() => setTab("cloud")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors ${
            currentTab === "cloud"
              ? "border-amber-600 text-amber-600 dark:text-amber-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Cloud className="w-4 h-4" />
          <span>Deye Cloud Sync</span>
          {deyeStatus?.is_configured && (
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
          )}
        </button>
        <button
          onClick={() => setTab("preview")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition-colors ${
            currentTab === "preview"
              ? "border-amber-600 text-amber-600 dark:text-amber-400 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <FileSearch className="w-4 h-4" />
          <span>Pre-Import Inspection</span>
        </button>
      </div>

      {currentTab === "datasets" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                  Batch Inverter Ingestion
                </h2>
                <span className="text-xs text-slate-500">Supports simultaneous .xlsx, .xlsm, .csv uploads</span>
              </div>

              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    processFileList(Array.from(e.dataTransfer.files));
                  }
                }}
                className={`p-8 border-2 border-dashed rounded-xl text-center flex flex-col items-center justify-center transition-colors min-h-[190px] ${
                  isDragging
                    ? "border-amber-500 bg-amber-50/50 dark:bg-amber-950/20"
                    : "border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/30"
                }`}
              >
                {progress ? (
                  <div className="w-full max-w-md mx-auto space-y-3.5 py-1">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-amber-600 dark:text-amber-400" />
                        <span className="font-semibold text-slate-900 dark:text-slate-100">
                          Loading file {progress.current} of {progress.total}
                        </span>
                      </div>
                      <span className="font-mono font-bold tabular-nums text-amber-600 dark:text-amber-400 text-sm">
                        {progress.percent}%
                      </span>
                    </div>

                    <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3 overflow-hidden shadow-inner p-0.5 border border-slate-300 dark:border-slate-600">
                      <div
                        className="bg-amber-600 dark:bg-amber-500 h-full rounded-full transition-all duration-300 ease-out"
                        style={{ width: `${progress.percent}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span className="truncate max-w-[210px] text-left">
                        Processing: <strong className="font-mono text-slate-700 dark:text-slate-300">{progress.currentFileName}</strong>
                      </span>
                      <span className="font-medium text-slate-700 dark:text-slate-300">
                        {progress.estimatedRemainingSec !== null && progress.estimatedRemainingSec > 0
                          ? `~${progress.estimatedRemainingSec}s remaining`
                          : progress.percent === 100
                          ? "Finalizing commit..."
                          : "Calculating finish time..."}
                      </span>
                    </div>
                  </div>
                ) : (
                  <>
                    <UploadCloud className="w-10 h-10 text-slate-400 mb-3" />
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Drag and drop multi-day inverter telemetry files here
                    </p>
                    <p className="text-xs text-slate-500 mb-4">
                      Batch uploads automatically check SHA-256 fingerprints and merge timeline continuous signals.
                    </p>
                    <label className="cursor-pointer px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors">
                      Browse Files
                      <input
                        type="file"
                        multiple
                        accept=".xlsx,.xlsm,.csv"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files && e.target.files.length > 0) {
                            processFileList(Array.from(e.target.files));
                          }
                        }}
                      />
                    </label>
                  </>
                )}
              </div>

              {uploadStatus && (
                <div className="mt-4 p-3 bg-slate-100 dark:bg-slate-800/80 rounded-lg text-xs flex items-center justify-between text-slate-700 dark:text-slate-300">
                  <span>{uploadStatus}</span>
                  <button
                    onClick={() => setUploadStatus(null)}
                    className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    Dismiss
                  </button>
                </div>
              )}
            </div>

            <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-4">
                  Library Provenance
                </h2>
                <div className="space-y-4">
                  <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800 text-sm">
                    <span className="text-slate-500">Total Telemetry Files</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">{sources.length}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800 text-sm">
                    <span className="text-slate-500">Committed Records</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">{totalRecords.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800 text-sm">
                    <span className="text-slate-500">Included in Portfolio</span>
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">{includedSources.length}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 text-sm">
                    <span className="text-slate-500">Excluded or Uncommitted</span>
                    <span className="font-semibold text-amber-600 dark:text-amber-400">{excludedSources.length}</span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 dark:border-slate-800 text-xs text-slate-500 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span>Deterministic SHA-256 deduplication active</span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="flex bg-slate-100 dark:bg-slate-800 rounded-lg p-1 text-xs font-medium">
                  <button
                    onClick={() => setFilterTab("all")}
                    className={`px-3 py-1.5 rounded-md transition-colors ${
                      filterTab === "all" ? "bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    All ({sources.length})
                  </button>
                  <button
                    onClick={() => setFilterTab("included")}
                    className={`px-3 py-1.5 rounded-md transition-colors ${
                      filterTab === "included" ? "bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    Included ({includedSources.length})
                  </button>
                  <button
                    onClick={() => setFilterTab("excluded")}
                    className={`px-3 py-1.5 rounded-md transition-colors ${
                      filterTab === "excluded" ? "bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    Excluded ({excludedSources.length})
                  </button>
                  {pendingSources.length > 0 && (
                    <button
                      onClick={() => setFilterTab("pending")}
                      className={`px-3 py-1.5 rounded-md transition-colors ${
                        filterTab === "pending" ? "bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 font-semibold" : "text-amber-600 dark:text-amber-400"
                      }`}
                    >
                      Pending ({pendingSources.length})
                    </button>
                  )}
                </div>
              </div>

              {selectedIds.size > 0 && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500 font-medium">{selectedIds.size} selected:</span>
                  <button
                    onClick={() => handleBulkInclude(true)}
                    className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded font-medium transition-colors"
                  >
                    Include
                  </button>
                  <button
                    onClick={() => handleBulkInclude(false)}
                    className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded font-medium transition-colors"
                  >
                    Exclude
                  </button>
                  <button
                    onClick={() => setIsBulkDeleting(true)}
                    className="px-2.5 py-1.5 bg-red-50 hover:bg-red-100 dark:bg-red-950/40 text-red-600 dark:text-red-400 rounded font-medium transition-colors"
                  >
                    Delete ({selectedIds.size})
                  </button>
                </div>
              )}
            </div>

            {filteredSources.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <Database className="w-8 h-8 mx-auto mb-2 text-slate-400 opacity-60" />
                <p className="text-sm font-medium">No datasets found in this view.</p>
                <p className="text-xs text-slate-400 mt-1">Upload inverter files to populate the historical portfolio.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="px-4 py-3 w-10">
                        <input
                          type="checkbox"
                          checked={allFilteredSelected}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedIds(new Set(filteredSources.map(s => s.id)));
                            } else {
                              setSelectedIds(new Set());
                            }
                          }}
                          className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                        />
                      </th>
                      <th className="px-4 py-3">Source File</th>
                      <th className="px-4 py-3">Telemetry Time Range</th>
                      <th className="px-4 py-3">Records</th>
                      <th className="px-4 py-3">Portfolio Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredSources.map((src) => {
                      const isSelected = selectedIds.has(src.id);
                      const isActive = activeDatasetId === src.id;
                      const isPending = src.total_rows === 0 || !src.start_time;

                      return (
                        <tr
                          key={src.id}
                          className={`hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors ${
                            isActive ? "bg-amber-50/40 dark:bg-amber-950/20" : ""
                          }`}
                        >
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                const next = new Set(selectedIds);
                                if (e.target.checked) next.add(src.id);
                                else next.delete(src.id);
                                setSelectedIds(next);
                              }}
                              className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                            />
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-slate-900 dark:text-slate-100 flex items-center gap-2">
                              <span>{src.filename}</span>
                              {isActive && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 font-semibold border border-amber-300 dark:border-amber-800">
                                  ACTIVE
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">
                              {src.file_hash ? `${src.file_hash.slice(0, 12)}...` : "Unindexed"}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-400">
                            {src.start_time ? (
                              <span>
                                {format12HourDateTime(src.start_time)} to {format12HourDateTime(src.end_time || src.start_time)}
                              </span>
                            ) : (
                              <span className="text-amber-600 dark:text-amber-400 font-medium">Pending ingestion commit</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs font-mono">
                            {(src.total_rows || 0).toLocaleString()}
                          </td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => handleToggleInclude(src.id, src.is_included)}
                              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                                src.is_included === 1
                                  ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400"
                                  : "bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-slate-700"
                              }`}
                            >
                              {src.is_included === 1 ? "Included" : "Excluded"}
                            </button>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              {isPending ? (
                                <button
                                  onClick={() => handleAutoCommitSingle(src.id)}
                                  disabled={committingId === src.id}
                                  className="px-2.5 py-1 text-xs font-medium rounded bg-amber-600 hover:bg-amber-700 text-white transition-colors disabled:opacity-50 flex items-center gap-1"
                                >
                                  <Play className="w-3 h-3" />
                                  {committingId === src.id ? "Committing..." : "Commit"}
                                </button>
                              ) : (
                                <button
                                  onClick={() => setActiveDatasetId(src.id)}
                                  className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                                    isActive
                                      ? "bg-amber-600 text-white"
                                      : "bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                                  }`}
                                >
                                  {isActive ? "Active" : "Select"}
                                </button>
                              )}
                              <button
                                onClick={() => setDeleteTarget(src)}
                                className="p-1 text-slate-400 hover:text-red-600 transition-colors"
                                title="Delete Source"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {currentTab === "cloud" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Radio className="w-5 h-5 text-amber-600" />
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                    Station & Device Hierarchy
                  </h2>
                </div>
                <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400">
                  {deyeStatus?.device_hierarchy?.logger?.status || "ONLINE"}
                </span>
              </div>

              <div className="space-y-3.5 text-xs">
                <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                  <div className="font-semibold text-slate-800 dark:text-slate-200">
                    {deyeStatus?.device_hierarchy?.installation_name || "SolarScope Primary Station"}
                  </div>
                  <div className="text-slate-500 font-mono text-[11px] mt-0.5">
                    Station ID: {deyeStatus?.station_id || "STATION-2026"}
                  </div>
                </div>

                <div className="flex items-center justify-center py-0.5 text-slate-400">
                  <ArrowRight className="w-4 h-4 rotate-90" />
                </div>

                <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800 dark:text-slate-200">Deye Data Logger</span>
                    <span className="font-mono text-emerald-600 font-medium">5-min interval</span>
                  </div>
                  <div className="text-slate-600 dark:text-slate-400 mt-1 font-mono">
                    Serial: {deyeStatus?.device_hierarchy?.logger?.logger_serial || "1251892903"}
                  </div>
                  <div className="text-slate-500 text-[11px] mt-0.5 font-mono">
                    Firmware: {deyeStatus?.device_hierarchy?.logger?.firmware_version || "MW4_32_5407_SS_04_00.00.00.13"}
                  </div>
                </div>

                <div className="flex items-center justify-center py-0.5 text-slate-400">
                  <ArrowRight className="w-4 h-4 rotate-90" />
                </div>

                <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800 dark:text-slate-200">Hybrid Inverter</span>
                    <span className="font-mono text-slate-600 dark:text-slate-400">6.0 kW continuous</span>
                  </div>
                  <div className="text-slate-600 dark:text-slate-400 mt-1 font-mono">
                    Serial: {deyeStatus?.device_hierarchy?.inverter?.inverter_serial || "2604282202"}
                  </div>
                  <div className="text-slate-500 text-[11px] mt-0.5">
                    Model: {deyeStatus?.device_hierarchy?.inverter?.model || "SUN-6K-SG06LP1-EU-CM2"}
                  </div>
                </div>
              </div>
            </div>

            <div className="md:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Cloud className="w-5 h-5 text-amber-600" />
                    <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                      Cloud Sync Operations & Status
                    </h2>
                  </div>
                  <span className="text-xs text-slate-500">
                    Policy: <strong className="text-slate-700 dark:text-slate-300 font-mono">Timestamp-Key Reconciliation</strong>
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <div className="text-xs text-slate-500">Last Telemetry Sync</div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-1">
                      {deyeStatus?.last_sync_time ? format12HourDateTime(deyeStatus.last_sync_time) : "None recorded"}
                    </div>
                  </div>
                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <div className="text-xs text-slate-500">Scheduled Polling</div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-1">
                      {deyeStatus?.auto_sync ? `Enabled (${deyeStatus.sync_interval_min || 5} min)` : "Manual On-Demand"}
                    </div>
                  </div>
                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <div className="text-xs text-slate-500">Offline Resilience</div>
                    <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
                      Buffered Cache Active
                    </div>
                  </div>
                </div>

                {deyeMessage && (
                  <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded-lg text-xs text-amber-800 dark:text-amber-300 mb-6 flex items-center justify-between">
                    <span>{deyeMessage}</span>
                    <button onClick={() => setDeyeMessage(null)} className="text-amber-600 hover:text-amber-800">
                      Dismiss
                    </button>
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-3">
                <button
                  onClick={handleTestDeyeConnection}
                  disabled={deyeTesting || deyeSyncing}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  {deyeTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}
                  <span>Test API Connection</span>
                </button>
                <button
                  onClick={handleSyncDeyeNow}
                  disabled={deyeTesting || deyeSyncing}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shadow-sm disabled:opacity-50"
                >
                  {deyeSyncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  <span>Trigger Incremental Sync</span>
                </button>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-amber-600" />
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  Deye Cloud / Solarman API Credentials
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 text-xs font-semibold rounded ${
                  deyeStatus?.is_configured
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-400"
                }`}>
                  {deyeStatus?.is_configured ? "Configured & Ready" : "Credentials Required"}
                </span>
                <button
                  type="button"
                  onClick={handleApplyDemoConfig}
                  className="px-2.5 py-1 text-xs rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium transition-colors"
                >
                  Use Demo Mode
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-500">
              Direct cloud sync polls telemetry from the Deye Cloud / Solarman Open API. If you do not have an API Developer account, you can click <strong>Use Demo Mode</strong> to simulate live synchronization, or upload Excel/CSV files directly in the Historical Datasets tab.
            </p>

            <form onSubmit={handleSaveDeyeConfig} className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs pt-1">
              <div>
                <label className="block font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Station ID
                </label>
                <input
                  type="text"
                  placeholder="e.g. STATION-2026"
                  value={configStationId}
                  onChange={(e) => setConfigStationId(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-600 dark:text-slate-400 mb-1">
                  App ID
                </label>
                <input
                  type="text"
                  placeholder="Open API App ID or 'demo'"
                  value={configAppId}
                  onChange={(e) => setConfigAppId(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-600 dark:text-slate-400 mb-1">
                  App Secret
                </label>
                <input
                  type="password"
                  placeholder="App Secret Key"
                  value={configAppSecret}
                  onChange={(e) => setConfigAppSecret(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Account Email / Username (Optional)
                </label>
                <input
                  type="text"
                  placeholder="user@example.com"
                  value={configUsername}
                  onChange={(e) => setConfigUsername(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Account Password (Optional)
                </label>
                <input
                  type="password"
                  placeholder="Account Password"
                  value={configPassword}
                  onChange={(e) => setConfigPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200"
                />
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={savingConfig}
                  className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-semibold transition-colors shadow-sm disabled:opacity-50"
                >
                  {savingConfig ? "Saving..." : "Save Credentials"}
                </button>
              </div>
            </form>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-4">
              Recent Synchronization Logs
            </h3>
            {deyeStatus?.recent_logs && deyeStatus.recent_logs.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-800/50 uppercase tracking-wider text-slate-500 font-semibold border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="px-4 py-2.5">Sync Timestamp</th>
                      <th className="px-4 py-2.5">Fetched Records</th>
                      <th className="px-4 py-2.5">Inserted Rows</th>
                      <th className="px-4 py-2.5">Status</th>
                      <th className="px-4 py-2.5">Diagnostics</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {deyeStatus.recent_logs.map(log => (
                      <tr key={log.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="px-4 py-2.5 font-mono text-slate-600 dark:text-slate-400">
                          {format12HourDateTime(log.sync_time)}
                        </td>
                        <td className="px-4 py-2.5 font-mono">{log.records_fetched}</td>
                        <td className="px-4 py-2.5 font-mono">{log.records_inserted}</td>
                        <td className="px-4 py-2.5">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            log.status === "SUCCESS"
                              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
                              : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400"
                          }`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-slate-500">
                          {log.error_message || "Reconciled against local database without conflict"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">
                No external cloud sync transactions logged yet. Click "Trigger Incremental Sync" to pull telemetry.
              </div>
            )}
          </div>
        </div>
      )}

      {currentTab === "preview" && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-2">
              Pre-Import Telemetry Inspection & Quality Verification
            </h2>
            <p className="text-xs text-slate-500 mb-6">
              Inspect an inverter spreadsheet or CSV file before committing it to the permanent library. Inspects SHA-256 fingerprint, sampling interval consistency, duplicate detection against database, and signal mapping.
            </p>

            <div className="p-8 border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl text-center bg-slate-50/50 dark:bg-slate-800/30">
              <FileSearch className="w-10 h-10 text-slate-400 mx-auto mb-3" />
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Select an inverter telemetry file to inspect
              </p>
              <p className="text-xs text-slate-500 mb-4">
                Accepts .xlsx, .xlsm, or .csv. Does not modify the database until you click Commit.
              </p>
              <label className="cursor-pointer px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors">
                Choose File to Inspect
                <input
                  type="file"
                  accept=".xlsx,.xlsm,.csv"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleInspectPreview(e.target.files[0]);
                    }
                  }}
                />
              </label>
            </div>

            {previewLoading && (
              <div className="py-12 flex flex-col items-center justify-center gap-2 text-slate-500">
                <Loader2 className="w-6 h-6 animate-spin text-amber-600" />
                <span className="text-xs font-medium">Computing cryptographic checksum and analyzing telemetry structure...</span>
              </div>
            )}

            {previewError && (
              <div className="mt-6 p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 rounded-xl text-xs text-red-700 dark:text-red-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{previewError}</span>
              </div>
            )}

            {previewResult && !previewLoading && (
              <div className="mt-6 space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500">Filename & Format</span>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-1 truncate">
                      {previewResult.filename}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                      {previewResult.file_format} • {(previewResult.filesize_bytes / 1024).toFixed(1)} KB
                    </div>
                  </div>

                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500">Observations & Interval</span>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-1 font-mono">
                      {previewResult.total_records.toLocaleString()} rows
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                      Sampling ~{previewResult.sampling_interval_min} min
                    </div>
                  </div>

                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500">Duplicate Check</span>
                    <div className="text-sm font-semibold mt-1 flex items-center gap-1.5">
                      {previewResult.is_duplicate ? (
                        <>
                          <AlertTriangle className="w-4 h-4 text-amber-600" />
                          <span className="text-amber-600 dark:text-amber-400">Already in Library</span>
                        </>
                      ) : (
                        <>
                          <Check className="w-4 h-4 text-emerald-600" />
                          <span className="text-emerald-600 dark:text-emerald-400">Unique Dataset</span>
                        </>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate mt-0.5">
                      {previewResult.file_hash.slice(0, 16)}...
                    </div>
                  </div>

                  <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500">Quality Index</span>
                    <div className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-1 font-mono">
                      {previewResult.quality_score} / 100
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      {previewResult.potential_issues.length === 0 ? "No anomalies detected" : `${previewResult.potential_issues.length} warnings`}
                    </div>
                  </div>
                </div>

                {previewResult.potential_issues.length > 0 && (
                  <div className="p-4 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-xl">
                    <div className="text-xs font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1.5 mb-2">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Ingestion Warnings</span>
                    </div>
                    <ul className="text-xs text-amber-700 dark:text-amber-400 space-y-1 list-disc list-inside">
                      {previewResult.potential_issues.map((issue, idx) => (
                        <li key={idx}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-100 dark:border-slate-800">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
                    Detected Signal Mappings
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    {Object.entries(previewResult.columns_detected).map(([canonical, header]) => (
                      <div key={canonical} className="p-2.5 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-800">
                        <div className="text-slate-400 font-mono text-[10px]">{canonical}</div>
                        <div className="font-semibold text-slate-800 dark:text-slate-200 truncate mt-0.5">{header}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    onClick={() => {
                      setPreviewResult(null);
                      setPreviewFile(null);
                    }}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-colors"
                  >
                    Discard
                  </button>
                  <button
                    onClick={handleCommitPreviewedFile}
                    disabled={uploading}
                    className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shadow-sm disabled:opacity-50"
                  >
                    {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                    <span>Commit to Historical Library</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Remove Dataset from Library"
        description="Are you sure you want to remove this dataset from the historical library? This operation permanently removes its telemetry from managed storage and recalculates all historical aggregations."
        confirmText="Remove Dataset"
        cancelText="Keep Dataset"
        variant="danger"
        loading={deleting}
        onConfirm={handleConfirmSingleDelete}
        onCancel={() => {
          if (!deleting) setDeleteTarget(null);
        }}
        itemDetails={deleteTarget ? [
          { label: "Filename", value: deleteTarget.filename },
          { label: "Format", value: deleteTarget.file_format || "XLSX" },
          { label: "Observations", value: `${(deleteTarget.total_rows || 0).toLocaleString()} records` },
          { label: "Time Span", value: deleteTarget.start_time ? `${format12HourDateTime(deleteTarget.start_time)} to ${format12HourDateTime(deleteTarget.end_time)}` : "Not committed" },
          { label: "SHA-256", value: deleteTarget.file_hash ? `${deleteTarget.file_hash.slice(0, 16)}...` : "N/A" }
        ] : undefined}
      />

      <ConfirmModal
        isOpen={isBulkDeleting}
        title={`Remove ${selectedIds.size} Selected Datasets`}
        description={`Are you sure you want to permanently remove the ${selectedIds.size} selected datasets from the historical library? Their telemetry observations will be deleted and multi-day summaries will be updated.`}
        confirmText={`Remove ${selectedIds.size} Datasets`}
        cancelText="Cancel"
        variant="danger"
        loading={deleting}
        onConfirm={handleConfirmBulkDelete}
        onCancel={() => {
          if (!deleting) setIsBulkDeleting(false);
        }}
        itemDetails={[
          { label: "Selected Count", value: `${selectedIds.size} files` },
          {
            label: "Files to Remove",
            value: sources.filter(s => selectedIds.has(s.id)).map(s => s.filename).slice(0, 3).join(", ") + (selectedIds.size > 3 ? ` + ${selectedIds.size - 3} more` : "")
          }
        ]}
      />
    </div>
  );
};
