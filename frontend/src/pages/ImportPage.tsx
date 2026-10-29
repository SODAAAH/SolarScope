import React, { useState, useEffect } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { api, type DatasetPreview, type ColumnItem } from '../lib/api';
import { UploadCloud, Check, ArrowRight, RefreshCw } from 'lucide-react';
import { formatTimeRange12 } from '../lib/formatters';

export const ImportPage: React.FC = () => {
  const { setActiveDatasetId } = useOutletContext<{ setActiveDatasetId: (id: string) => void }>();
  const [searchParams] = useSearchParams();
  const initialId = searchParams.get('dataset_id') || localStorage.getItem('solarscope_dataset_id') || '';

  const [datasetId, setDatasetId] = useState<string>(initialId);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [selectedSheet, setSelectedSheet] = useState<string>('');
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [signConventions, setSignConventions] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const CANONICAL_OPTIONS = [
    { value: 'timestamp', label: 'Timestamp / Datetime' },
    { value: 'pv_power_kw', label: 'Solar PV Power (kW)' },
    { value: 'load_power_kw', label: 'Household Load / Demand (kW)' },
    { value: 'grid_power_kw', label: 'Grid Power (kW)' },
    { value: 'battery_power_kw', label: 'Battery Power (kW)' },
    { value: 'soc_percent', label: 'Battery State of Charge (%)' },
    { value: 'generator_power_kw', label: 'Generator Power (kW)' },
    { value: 'grid_tied_inverter_power_kw', label: 'Grid-tied Inverter Power (kW)' },
    { value: 'ignore', label: 'Ignore / Duplicate' }
  ];

  const loadPreview = (id: string, sheet?: string) => {
    if (!id || id === 'all') return;
    setLoading(true);
    setError(null);
    api.getPreview(id, sheet)
      .then((data) => {
        setPreview(data);
        if (data.dataset_id && data.dataset_id !== id) {
          setDatasetId(data.dataset_id);
          setActiveDatasetId(data.dataset_id);
          localStorage.setItem('solarscope_dataset_id', data.dataset_id);
        }
        setSelectedSheet(data.selected_sheet);
        const initMap: Record<string, string> = {};
        const initSigns: Record<string, string> = {};
        data.columns.forEach((col: ColumnItem) => {
          if (col.is_duplicate) {
            initMap[col.original_name] = 'ignore';
          } else if (col.canonical_name) {
            initMap[col.original_name] = col.canonical_name;
          }
          if (col.sign_convention) {
            initSigns[col.canonical_name || col.original_name] = col.sign_convention;
          }
        });
        setMappings(initMap);
        setSignConventions(initSigns);
      })
      .catch(() => {
        localStorage.removeItem('solarscope_dataset_id');
        api.listSources().then((sources) => {
          if (sources && sources.length > 0) {
            setDatasetId(sources[0].id);
            setActiveDatasetId(sources[0].id);
          } else {
            setError(null);
            setPreview(null);
          }
        }).catch(() => {
          setError(null);
        });
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (!datasetId || datasetId === 'all') {
      api.listSources().then((sources) => {
        if (sources && sources.length > 0) {
          setDatasetId(sources[0].id);
        }
      }).catch(() => {});
    } else {
      loadPreview(datasetId);
    }
  }, [datasetId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.uploadDataset(file);
      setDatasetId(res.dataset_id);
      setActiveDatasetId(res.dataset_id);
      loadPreview(res.dataset_id, res.selected_sheet || undefined);
    } catch (err: any) {
      setError(err.message || 'File upload failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!datasetId || !preview) return;
    setCommitting(true);
    setError(null);
    try {
      const res = await api.commitDataset(datasetId, mappings, signConventions, selectedSheet);
      setCommitResult(res);
      setActiveDatasetId(datasetId);
    } catch (err: any) {
      setError(err.message || 'Failed to commit dataset mappings');
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-lg font-semibold tracking-tight">Dataset Ingestion & Quality Wizard</h1>
        <p className="text-xs text-slate-500">Upload raw solar inverter exports (.xlsx, .xlsm, .csv), review signal mapping, and audit sampling intervals.</p>
      </div>

      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 rounded text-xs">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 bg-white dark:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-700 rounded-lg text-center flex flex-col items-center justify-center">
          <UploadCloud className="h-8 w-8 text-slate-400 mb-2" />
          <p className="text-xs font-semibold mb-1">Select Inverter File</p>
          <p className="text-[11px] text-slate-500 mb-4">Supports .xlsx, .xlsm, .csv files</p>
          <label className="cursor-pointer bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-medium px-3 py-1.5 rounded-md transition-colors">
            {loading ? "Reading..." : "Browse File"}
            <input type="file" accept=".xlsx,.xlsm,.csv" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>

        <div className="md:col-span-2 p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-slate-700 dark:text-slate-300">Dataset Metadata</h2>
              {datasetId && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                  ID: {datasetId}
                </span>
              )}
            </div>
            {preview ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded">
                  <span className="text-[11px] text-slate-500 block">Filename</span>
                  <span className="font-semibold truncate block">{preview.filename}</span>
                </div>
                <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded">
                  <span className="text-[11px] text-slate-500 block">Total Records</span>
                  <span className="font-semibold tabular-nums block">{preview.total_rows}</span>
                </div>
                <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded">
                  <span className="text-[11px] text-slate-500 block">Time Span</span>
                  <span className="font-semibold text-[11px] block">{formatTimeRange12(preview.detected_start_time, preview.detected_end_time)}</span>
                </div>
                <div className="p-2 bg-slate-50 dark:bg-slate-800/50 rounded">
                  <span className="text-[11px] text-slate-500 block">Sheet</span>
                  <select
                    value={selectedSheet}
                    onChange={(e) => {
                      setSelectedSheet(e.target.value);
                      loadPreview(datasetId, e.target.value);
                    }}
                    className="text-xs font-semibold bg-transparent border-0 p-0 focus:ring-0 w-full"
                  >
                    {preview.available_sheets.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No file uploaded yet. Use the upload box or click "Load Sample" in the sidebar.</p>
            )}
          </div>

          {commitResult && (
            <div className="mt-4 p-3 bg-battery-50 dark:bg-battery-950/30 border border-battery-200 dark:border-battery-800 rounded text-xs text-battery-800 dark:text-battery-200 flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium">
                <Check className="h-4 w-4 text-battery-600" />
                Dataset normalized & verified. Quality score: {commitResult.quality_score}% ({commitResult.quality_status})
              </span>
            </div>
          )}
        </div>
      </div>

      {preview && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold text-slate-800 dark:text-slate-200">Column Meaning & Sign Mapping</h2>
              <p className="text-[11px] text-slate-500">Verify canonical signal assignments, sign conventions, and duplicate channel exclusions.</p>
            </div>
            <button
              onClick={handleCommit}
              disabled={committing}
              className="bg-solar-600 hover:bg-solar-700 text-white text-xs font-medium px-4 py-2 rounded-md transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {committing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
              {committing ? 'Normalizing...' : 'Commit Mapping & Run Audit'}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Original Header</th>
                  <th className="px-4 py-2.5 font-medium">Canonical Signal</th>
                  <th className="px-4 py-2.5 font-medium">Sign Convention</th>
                  <th className="px-4 py-2.5 font-medium">Status / Flag</th>
                  <th className="px-4 py-2.5 font-medium">Sample Values</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {preview.columns.map((col) => {
                  const currentCanonical = mappings[col.original_name] || '';
                  return (
                    <tr key={col.original_name} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                      <td className="px-4 py-2.5 font-mono text-[11px] text-slate-800 dark:text-slate-200 font-medium">
                        {col.original_name}
                      </td>
                      <td className="px-4 py-2.5">
                        <select
                          value={currentCanonical}
                          onChange={(e) => {
                            setMappings({ ...mappings, [col.original_name]: e.target.value });
                          }}
                          className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-2 py-1 focus:ring-1 focus:ring-solar-500"
                        >
                          <option value="">-- Unmapped --</option>
                          {CANONICAL_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2.5">
                        {currentCanonical === 'battery_power_kw' ? (
                          <select
                            value={signConventions['battery_power_kw'] || 'positive_discharge'}
                            onChange={(e) => setSignConventions({ ...signConventions, battery_power_kw: e.target.value })}
                            className="text-[11px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-2 py-1"
                          >
                            <option value="positive_discharge">+ Discharge / - Charge</option>
                            <option value="positive_charge">+ Charge / - Discharge</option>
                          </select>
                        ) : currentCanonical === 'grid_power_kw' ? (
                          <select
                            value={signConventions['grid_power_kw'] || 'positive_import'}
                            onChange={(e) => setSignConventions({ ...signConventions, grid_power_kw: e.target.value })}
                            className="text-[11px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-2 py-1"
                          >
                            <option value="positive_import">+ Import / - Export</option>
                            <option value="negative_import">- Import / + Export</option>
                          </select>
                        ) : (
                          <span className="text-slate-400 text-[11px]">Standard</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        {col.is_duplicate ? (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">
                            Duplicate of {col.duplicate_of}
                          </span>
                        ) : col.is_inactive ? (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            Inactive Channel (0.0 kW)
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-battery-50 dark:bg-battery-950/40 text-battery-700 dark:text-battery-300">
                            Active (Conf: {Math.round(col.confidence * 100)}%)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-slate-500 tabular-nums">
                        {col.sample_values?.slice(0, 3).join(', ') || 'N/A'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
