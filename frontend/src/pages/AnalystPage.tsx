import React, { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import { BookOpen, Search } from "lucide-react";
import { api, type AnalystPresetQuery, type AnalystResponse } from "../lib/api";

interface OutletContextType {
  activeDatasetId: string | null;
}

export const AnalystPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [presets, setPresets] = useState<AnalystPresetQuery[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>("why_battery_drained");
  const [customText, setCustomText] = useState<string>("");
  const [analysisResult, setAnalysisResult] = useState<AnalystResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getAnalystPresets()
      .then((data) => {
        setPresets(data);
        if (data.length > 0 && activeDatasetId) {
          runAnalysis(data[0].id, data[0].question);
        }
      })
      .catch(console.error);
  }, []);

  const runAnalysis = async (key: string, text?: string) => {
    if (!activeDatasetId) return;
    setSelectedKey(key);
    setLoading(true);
    try {
      const res = await api.queryAnalyst(activeDatasetId, key, text || "");
      setAnalysisResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!activeDatasetId) {
    return (
      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <BookOpen className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">No Dataset Active</h3>
        <p className="text-sm text-slate-500 mt-1">Select an active dataset to run energy systems diagnostics.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Energy Systems Diagnostic Advisor
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Evidence-based household energy analytics answering specific behavioral questions backed by physical measurements.
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Diagnostic Questions
        </h2>
        <div className="flex flex-wrap gap-2">
          {presets.map((item) => (
            <button
              key={item.id}
              onClick={() => runAnalysis(item.id, item.question)}
              className={`px-3.5 py-2 text-xs rounded-lg font-medium transition-colors text-left flex items-center gap-2 ${
                selectedKey === item.id
                  ? "bg-amber-600 text-white font-semibold"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              <span>{item.question}</span>
            </button>
          ))}
        </div>

        <div className="pt-2 flex gap-2">
          <input
            type="text"
            placeholder="Type a custom inquiry regarding your battery, grid purchases, or solar yield..."
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && customText.trim()) {
                runAnalysis("custom_query", customText);
              }
            }}
            className="flex-1 px-3.5 py-2 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
          <button
            onClick={() => customText.trim() && runAnalysis("custom_query", customText)}
            disabled={loading || !customText.trim()}
            className="px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:bg-slate-800 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            <Search className="w-3.5 h-3.5" />
            <span>Analyze</span>
          </button>
        </div>
      </div>

      {loading && (
        <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-slate-500 font-mono">
          Verifying electrical measurements and compiling diagnostic findings...
        </div>
      )}

      {analysisResult && !loading && (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden divide-y divide-slate-100 dark:divide-slate-800">
          <div className="p-6 bg-slate-50 dark:bg-slate-800/40">
            <div className="flex justify-between items-start gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                  Diagnostic Finding
                </span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                  {analysisResult.title}
                </h3>
              </div>
              <span className="px-2.5 py-1 text-xs rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 font-medium">
                {analysisResult.confidence_level}
              </span>
            </div>
          </div>

          <div className="p-6 space-y-6 text-xs text-slate-700 dark:text-slate-300">
            <div>
              <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                1. What happened?
              </span>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                {analysisResult.what_happened}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                2. What does the data show?
              </span>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed font-mono">
                {analysisResult.what_data_shows}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                3. Why did it happen?
              </span>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                {analysisResult.why_it_happened}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                4. Energy & Financial Impact
              </span>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed font-mono">
                {analysisResult.energy_or_money_impact}
              </p>
            </div>

            <div className="p-4 bg-amber-50 dark:bg-amber-950/20 rounded-lg border border-amber-200 dark:border-amber-900/40">
              <span className="font-semibold text-amber-900 dark:text-amber-200 block mb-1">
                5. Recommended Action for Homeowner
              </span>
              <p className="text-amber-800 dark:text-amber-300 leading-relaxed">
                {analysisResult.what_to_do}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
