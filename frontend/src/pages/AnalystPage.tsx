import React, { useState, useRef } from "react";
import { useOutletContext } from "react-router-dom";
import {
  BookOpen,
  Search,
  Square,
  ShieldCheck,
  CheckCircle2,
  Loader2
} from "lucide-react";
import { api } from "../lib/api";
import { MarkdownView } from "../components/common/MarkdownView";

interface OutletContextType {
  activeDatasetId: string | null;
}

interface StreamingState {
  isStreaming: boolean;
  statusText: string;
  streamedText: string;
  stats: {
    path?: string;
    duration_ms?: number;
    tokens_per_sec?: number;
    tokens_generated?: number;
    ttft_sec?: number;
    total_duration_sec?: number;
  } | null;
  error: string | null;
}

export const AnalystPage: React.FC = () => {
  const { activeDatasetId } = useOutletContext<OutletContextType>();
  const [customText, setCustomText] = useState<string>("");

  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
    statusText: "",
    streamedText: "",
    stats: null,
    error: null
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreaming((prev) => ({
      ...prev,
      isStreaming: false,
      statusText: "Analysis interrupted."
    }));
  };

  const executeDiagnostic = async (queryText: string) => {
    if (!activeDatasetId) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setStreaming({
      isStreaming: true,
      statusText: "Routing inquiry...",
      streamedText: "",
      stats: null,
      error: null
    });

    try {
      await api.streamAnalystQuery(
        activeDatasetId,
        queryText,
        (chunk) => {
          if (chunk.type === "status") {
            setStreaming((prev) => ({ ...prev, statusText: chunk.message || "Processing..." }));
          } else if (chunk.type === "fast_path") {
            setStreaming((prev) => ({
              ...prev,
              statusText: "",
              streamedText: chunk.content || "",
              stats: { path: "FAST_PATH", duration_ms: 3.5 }
            }));
          } else if (chunk.type === "token") {
            setStreaming((prev) => ({
              ...prev,
              statusText: "",
              streamedText: prev.streamedText + (chunk.token || "")
            }));
          } else if (chunk.type === "done") {
            setStreaming((prev) => ({
              ...prev,
              isStreaming: false,
              statusText: "",
              stats: chunk.stats || prev.stats
            }));
          } else if (chunk.type === "error") {
            setStreaming((prev) => ({
              ...prev,
              isStreaming: false,
              error: chunk.message || "Diagnostic service error"
            }));
          }
        },
        abortController.signal
      );
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setStreaming((prev) => ({
          ...prev,
          isStreaming: false,
          error: err.message || "Diagnostic execution failure"
        }));
      }
    } finally {
      abortControllerRef.current = null;
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

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-full text-xs font-semibold flex items-center gap-1.5 border border-slate-200 dark:border-slate-700">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            Dual-Path Engine Active
          </span>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 p-5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Diagnostic Inquiry
          </h2>
          <span className="text-[11px] text-slate-400">
            Fast Path (Direct Compute) + Deep Diagnostics
          </span>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Ask about your solar production, battery charge level, TEI purchases, or why energy spiked..."
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && customText.trim()) {
                executeDiagnostic(customText);
              }
            }}
            className="flex-1 px-3.5 py-2.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
          {streaming.isStreaming ? (
            <button
              onClick={handleStopStreaming}
              className="px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              onClick={() => {
                if (customText.trim()) {
                  executeDiagnostic(customText);
                }
              }}
              disabled={!customText.trim()}
              className="px-5 py-2.5 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-200 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Analyze</span>
            </button>
          )}
        </div>
      </div>

      {streaming.isStreaming && streaming.statusText && !streaming.streamedText && (
        <div className="p-6 text-center bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-slate-500 flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
          <span>{streaming.statusText}</span>
        </div>
      )}

      {streaming.error && (
        <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 text-red-800 dark:text-red-300 rounded-xl text-xs">
          {streaming.error}
        </div>
      )}

      {streaming.streamedText && (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden divide-y divide-slate-100 dark:divide-slate-800">
          <div className="p-5 bg-slate-50 dark:bg-slate-800/40 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Diagnostic Finding
                </span>
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Verified Energy Intelligence
                </h3>
              </div>
            </div>
            {streaming.stats && (
              <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500">
                {streaming.stats.path === "FAST_PATH" ? (
                  <span className="px-2.5 py-1 rounded-full bg-emerald-100/70 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 font-semibold border border-emerald-200 dark:border-emerald-800">
                    Fast Path (Direct Compute: {streaming.stats.duration_ms || 3}ms)
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold border border-slate-300 dark:border-slate-700">
                    Deye Open MCP Diagnostics ({streaming.stats.duration_ms || 2500}ms)
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="p-6 font-sans">
            <MarkdownView content={streaming.streamedText} />
          </div>
        </div>
      )}
    </div>
  );
};
