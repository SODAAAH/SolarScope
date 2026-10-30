import React, { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
  UploadCloud,
  Trash2,
  RefreshCw,
  CheckCircle2,
  Play,
  AlertCircle,
  Loader2,
  CheckSquare,
  Filter,
  Layers
} from "lucide-react";
import { api, type SourceItem } from "../lib/api";
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

  useEffect(() => {
    fetchSources();
  }, []);

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

    const totalElapsed = Math.max(1, Math.round((Date.now() - startTime) / 1000));
    setProgress(null);
    setCommittingAll(false);
    setUploadStatus(`Committed ${committedCount} of ${total} pending file(s) in ${totalElapsed}s.`);
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

  const handleBulkCommitSelected = async () => {
    const pendingSelected = sources.filter(s => selectedIds.has(s.id) && (s.total_rows === 0 || !s.start_time));
    if (pendingSelected.length === 0) return;
    setCommittingAll(true);
    setUploadStatus(null);
    let committedCount = 0;
    for (let i = 0; i < pendingSelected.length; i++) {
      const src = pendingSelected[i];
      try {
        await api.autoCommitDataset(src.id);
        committedCount++;
        await fetchSources();
      } catch (err: any) {
        setUploadStatus(`Error committing ${src.filename}: ${err.message}`);
        break;
      }
    }
    setCommittingAll(false);
    setUploadStatus(`Committed ${committedCount} selected dataset(s).`);
  };

  const totalRecords = sources.reduce((acc, s) => acc + (s.total_rows || 0), 0);
  const includedSources = sources.filter(s => s.is_included === 1);
  const pendingSources = sources.filter(s => (s.total_rows === 0 || !s.start_time));
  const excludedSources = sources.filter(s => s.is_included !== 1);

  const hashCounts = sources.reduce((acc, s) => {
    if (s.file_hash) acc[s.file_hash] = (acc[s.file_hash] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

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
            Historical Data Library & Source Management
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Multi-file ingestion, SHA-256 fingerprinting, overlap resolution, and multi-day provenance tracking.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pendingSources.length > 0 && (
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
            onClick={fetchSources}
            disabled={loading}
            className="px-3 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

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

                <div className="text-[11px] text-slate-400 text-center">
                  Parsing telemetry channels, validating energy balance, and committing to storage
                </div>
              </div>
            ) : (
              <>
                <UploadCloud className="w-10 h-10 text-amber-500 mb-3" />
                <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                  Drag & Drop or Select Multiple Files
                </h3>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  Upload multiple single-day or multi-day files at once. Identical files are detected via SHA-256 fingerprinting.
                </p>
                <label className="cursor-pointer px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg transition-colors">
                  Select Files to Ingest
                  <input
                    type="file"
                    multiple
                    accept=".xlsx,.xlsm,.csv"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        processFileList(Array.from(e.target.files));
                      }
                    }}
                    disabled={uploading}
                    className="hidden"
                  />
                </label>
              </>
            )}
          </div>

          {uploadStatus && (
            <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200 rounded-lg flex items-center justify-between">
              <span>{uploadStatus}</span>
              <button
                onClick={() => setUploadStatus(null)}
                className="text-xs text-amber-600 hover:text-amber-800 dark:text-amber-300 underline ml-2"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-4">
              Historical Library Stats
            </h2>
            <div className="space-y-4">
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                <span className="text-xs text-slate-500">Total Sources Ingested</span>
                <div className="text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 mt-1">
                  {sources.length} files
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                <span className="text-xs text-slate-500">Included in Historical Aggregation</span>
                <div className="text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400 mt-1">
                  {includedSources.length} active
                </div>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                <span className="text-xs text-slate-500">Total Telemetry Observations</span>
                <div className="text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400 mt-1">
                  {totalRecords.toLocaleString()} rows
                </div>
              </div>

              {pendingSources.length > 0 && (
                <div className="p-3 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-900 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-amber-700 dark:text-amber-300 font-medium">Pending Uncommitted</span>
                    <div className="text-lg font-bold text-amber-800 dark:text-amber-200">
                      {pendingSources.length} files
                    </div>
                  </div>
                  <button
                    onClick={handleAutoCommitAll}
                    disabled={committingAll || uploading}
                    className="px-2.5 py-1 text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white rounded transition-colors disabled:opacity-50"
                  >
                    {committingAll ? "Working..." : "Commit All"}
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 text-[11px] text-slate-400 border-t border-slate-100 dark:border-slate-800 pt-3">
            All sources are fingerprinted and stored in local managed storage.
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Source Inventory & Provenance Records
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Review recognized formats, observation spans, quality scores, and inclusion flags.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setFilterTab("all")}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                filterTab === "all"
                  ? "bg-amber-600 text-white font-semibold"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>All ({sources.length})</span>
            </button>
            <button
              onClick={() => setFilterTab("included")}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                filterTab === "included"
                  ? "bg-emerald-600 text-white font-semibold"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Included ({includedSources.length})</span>
            </button>
            <button
              onClick={() => setFilterTab("excluded")}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                filterTab === "excluded"
                  ? "bg-slate-700 text-white font-semibold"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Excluded ({excludedSources.length})</span>
            </button>
            {pendingSources.length > 0 && (
              <button
                onClick={() => setFilterTab("pending")}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                  filterTab === "pending"
                    ? "bg-amber-600 text-white font-semibold"
                    : "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/40 border border-amber-200 dark:border-amber-800"
                }`}
              >
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Pending ({pendingSources.length})</span>
              </button>
            )}
          </div>
        </div>

        {selectedIds.size > 0 && (
          <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-800 flex flex-wrap items-center justify-between gap-3 animate-in fade-in slide-in-from-top-1">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span className="text-xs font-semibold text-amber-900 dark:text-amber-100">
                {selectedIds.size} dataset{selectedIds.size > 1 ? "s" : ""} selected
              </span>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => handleBulkInclude(true)}
                className="px-2.5 py-1 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded transition-colors"
              >
                Include in Analysis
              </button>
              <button
                onClick={() => handleBulkInclude(false)}
                className="px-2.5 py-1 text-xs font-medium bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-200 rounded transition-colors"
              >
                Exclude from Analysis
              </button>
              {sources.some(s => selectedIds.has(s.id) && (s.total_rows === 0 || !s.start_time)) && (
                <button
                  onClick={handleBulkCommitSelected}
                  disabled={committingAll}
                  className="px-2.5 py-1 text-xs font-medium bg-amber-600 hover:bg-amber-700 text-white rounded transition-colors disabled:opacity-50"
                >
                  Commit Selected
                </button>
              )}
              <button
                onClick={() => setIsBulkDeleting(true)}
                className="px-2.5 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded transition-colors flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                <span>Delete Selected</span>
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="px-2 py-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              >
                Clear Selection
              </button>
            </div>
          </div>
        )}

        {filteredSources.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-xs">
            {sources.length === 0
              ? "No datasets uploaded yet. Ingest your inverter files above to get started."
              : "No datasets match the selected filter."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold w-10">
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
                      className="rounded border-slate-300 text-amber-600 focus:ring-amber-500 cursor-pointer"
                      title={allFilteredSelected ? "Deselect All" : "Select All Filtered"}
                    />
                  </th>
                  <th className="px-4 py-3 font-semibold">Include in Aggregation</th>
                  <th className="px-4 py-3 font-semibold">Filename</th>
                  <th className="px-4 py-3 font-semibold">Format</th>
                  <th className="px-4 py-3 font-semibold">Records</th>
                  <th className="px-4 py-3 font-semibold">Time Span</th>
                  <th className="px-4 py-3 font-semibold">Quality</th>
                  <th className="px-4 py-3 font-semibold">SHA-256 Fingerprint</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredSources.map(src => {
                  const isActive = activeDatasetId === src.id;
                  const isInc = src.is_included === 1;
                  const isPending = src.total_rows === 0 || !src.start_time;
                  const isDup = Boolean(src.file_hash && hashCounts[src.file_hash] > 1);
                  const isChecked = selectedIds.has(src.id);

                  return (
                    <tr
                      key={src.id}
                      className={`hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors ${
                        isChecked
                          ? "bg-amber-50/60 dark:bg-amber-950/30"
                          : isActive
                          ? "bg-amber-50/30 dark:bg-amber-950/20"
                          : ""
                      }`}
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {
                            setSelectedIds(prev => {
                              const next = new Set(prev);
                              if (next.has(src.id)) {
                                next.delete(src.id);
                              } else {
                                next.add(src.id);
                              }
                              return next;
                            });
                          }}
                          className="rounded border-slate-300 text-amber-600 focus:ring-amber-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => handleToggleInclude(src.id, src.is_included)}
                          className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
                            isInc
                              ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                              : "bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700"
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${isInc ? "bg-emerald-500" : "bg-slate-400"}`} />
                          <span>{isInc ? "Active" : "Excluded"}</span>
                        </button>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                        <div className="flex items-center gap-2">
                          <span className="truncate max-w-xs">{src.filename}</span>
                          {src.sheet_name && (
                            <span className="text-[10px] bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
                              {src.sheet_name}
                            </span>
                          )}
                          {isDup && (
                            <span className="text-[10px] bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-1.5 py-0.5 rounded font-medium">
                              Duplicate
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                          {src.file_format || "XLSX"}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums">
                        {src.total_rows > 0 ? (
                          src.total_rows.toLocaleString()
                        ) : (
                          <span className="text-amber-600 dark:text-amber-400 font-semibold">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                        {src.start_time ? (
                          <span>
                            {format12HourDateTime(src.start_time)} to {format12HourDateTime(src.end_time)}
                          </span>
                        ) : (
                          <span className="text-amber-600 dark:text-amber-400 font-medium">Not committed</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {!isPending ? (
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                            src.quality_score >= 80
                              ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300"
                              : "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300"
                          }`}>
                            {src.quality_score > 0 ? `${src.quality_score.toFixed(0)}%` : "0%"}
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 flex items-center gap-1 w-fit">
                            <AlertCircle className="w-3 h-3 text-amber-600" />
                            Pending
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-[10px] text-slate-400 truncate max-w-[120px]" title={src.file_hash}>
                        {src.file_hash ? `${src.file_hash.slice(0, 10)}...` : "N/A"}
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
