import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../lib/api';
import { format12HourDateTime } from '../lib/formatters';

export const AnomaliesPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<{ activeDatasetId: string }>();
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');

  useEffect(() => {
    if (!activeDatasetId) return;
    setLoading(true);
    api.getAnomalies(activeDatasetId)
      .then(setAnomalies)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeDatasetId]);

  if (!activeDatasetId) {
    return <div className="p-8 text-center text-xs text-slate-500">Please select or import a dataset first.</div>;
  }

  const filtered = anomalies.filter(a => filterSeverity === 'ALL' || a.severity === filterSeverity);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Statistical Anomaly & Event Detection</h1>
          <p className="text-xs text-slate-500">Heuristic and statistical change-point detection across load spikes, unexpected grid interactions, and flatlined sensors.</p>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-slate-500">Severity:</span>
          {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
            <button
              key={sev}
              onClick={() => setFilterSeverity(sev)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                filterSeverity === sev
                  ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <h2 className="text-xs font-semibold">Detected Anomaly Events ({filtered.length})</h2>
          <span className="text-[11px] text-slate-500 font-mono">Statistical Confidence ≥ 75%</span>
        </div>

        {filtered.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            {loading ? 'Evaluating anomaly detectors...' : 'No anomalous events matching the selected severity.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Timestamp</th>
                  <th className="px-4 py-2.5 font-medium">Severity</th>
                  <th className="px-4 py-2.5 font-medium">Event Type</th>
                  <th className="px-4 py-2.5 font-medium">Observed Value</th>
                  <th className="px-4 py-2.5 font-medium">Confidence</th>
                  <th className="px-4 py-2.5 font-medium">Physical Description & Reasoning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filtered.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-2.5 font-mono text-[11px] text-slate-700 dark:text-slate-300">
                      {item.timestamp_12h || format12HourDateTime(item.timestamp)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        item.severity === 'HIGH'
                          ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300'
                          : item.severity === 'MEDIUM'
                          ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                      }`}>
                        {item.severity}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] font-medium text-slate-800 dark:text-slate-200">
                      {item.type}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] tabular-nums">
                      {item.value} kW
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] tabular-nums">
                      {Math.round(item.confidence * 100)}%
                    </td>
                    <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400 text-[11px] leading-relaxed">
                      {item.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
