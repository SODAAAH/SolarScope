import React, { useState } from 'react';
import { HelpCircle, X, ChevronRight, type LucideIcon } from 'lucide-react';
import { getTerm, type ViewMode } from '../../lib/terminology';

interface MetricCardProps {
  termId: string;
  value: string | number;
  unit?: string;
  viewMode?: ViewMode;
  customSimpleLabel?: string;
  customExplanation?: string;
  plainExplanation?: string;
  subtext?: string;
  changeDelta?: string;
  isPositiveDelta?: boolean;
  icon?: LucideIcon;
  accentColor?: 'solar' | 'teal' | 'coral' | 'slate';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  termId,
  value,
  unit,
  viewMode = 'simple',
  customSimpleLabel,
  customExplanation,
  plainExplanation,
  subtext,
  changeDelta,
  isPositiveDelta,
  icon: Icon,
  accentColor = 'solar'
}) => {
  const [showHelp, setShowHelp] = useState(false);
  const term = getTerm(termId);

  const isSimple = viewMode === 'simple';
  const label = isSimple ? (customSimpleLabel || term.simpleLabel) : term.technicalLabel;
  const displayUnit = unit || term.unit || '';
  const explanation = plainExplanation || customExplanation || term.simpleExplanation;

  const colorClasses = {
    solar: {
      border: 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700',
      iconBg: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
      badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
    },
    teal: {
      border: 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700',
      iconBg: 'bg-teal-500/10 text-teal-600 dark:text-teal-400',
      badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
    },
    coral: {
      border: 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700',
      iconBg: 'bg-orange-500/10 text-orange-600 dark:text-orange-400',
      badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
    },
    slate: {
      border: 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700',
      iconBg: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
      badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
    }
  }[accentColor];

  const provenanceBadgeColor = {
    Measured: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    Calculated: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    Estimated: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    Simulated: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
  }[term.provenance];

  return (
    <div className={`relative p-4 rounded-xl border bg-white dark:bg-slate-900 shadow-sm transition-all hover:shadow-md ${colorClasses.border}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          {Icon && (
            <div className={`p-1.5 rounded-md ${colorClasses.iconBg}`}>
              <Icon className="w-4 h-4" />
            </div>
          )}
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 leading-tight">
            {label}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${provenanceBadgeColor}`}>
            {term.provenance}
          </span>
          <button
            onClick={() => setShowHelp(true)}
            aria-label="How is this calculated?"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 rounded transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="flex items-baseline gap-1.5 mt-2">
        <span className="text-2xl font-bold tracking-tight font-mono tabular-nums text-slate-900 dark:text-white">
          {value}
        </span>
        {displayUnit && (
          <span className="text-xs font-medium text-slate-500">
            {displayUnit}
          </span>
        )}
      </div>

      {changeDelta && (
        <div className="mt-1 flex items-center gap-1 text-[11px]">
          <span className={`font-semibold tabular-nums ${isPositiveDelta ? 'text-emerald-600 dark:text-emerald-400' : 'text-orange-600 dark:text-orange-400'}`}>
            {changeDelta}
          </span>
          <span className="text-slate-400 text-[10px]">vs previous period</span>
        </div>
      )}

      {isSimple ? (
        <p className="mt-2.5 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/80 pt-2">
          {explanation}
        </p>
      ) : (
        <div className="mt-2.5 text-[11px] leading-relaxed text-slate-600 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/80 pt-2 space-y-1">
          {term.formula && (
            <div className="font-mono text-[10px] bg-slate-50 dark:bg-slate-800/60 p-1 rounded text-slate-700 dark:text-slate-300">
              {term.formula}
            </div>
          )}
          <div className="text-[10px] text-slate-500">
            {term.technicalDefinition}
          </div>
        </div>
      )}

      {subtext && (
        <div className="mt-1 text-[10px] text-slate-400 flex items-center gap-1">
          <ChevronRight className="w-2.5 h-2.5" />
          <span>{subtext}</span>
        </div>
      )}

      {showHelp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 max-w-md w-full shadow-2xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                  {term.simpleLabel}
                </h3>
                <span className="text-[11px] font-mono text-slate-400">
                  Technical: {term.technicalLabel}
                </span>
              </div>
              <button
                onClick={() => setShowHelp(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-0.5">
                  Plain-Language Meaning
                </span>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                  {term.simpleExplanation}
                </p>
              </div>

              <div>
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-0.5">
                  How SolarScope Calculates It
                </span>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                  {term.technicalDefinition}
                </p>
                {term.formula && (
                  <div className="mt-1.5 font-mono text-[11px] bg-slate-50 dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200">
                    Formula: {term.formula}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between text-[11px] pt-2 border-t border-slate-100 dark:border-slate-800 text-slate-500">
                <span>Unit: <strong className="font-mono text-slate-800 dark:text-slate-200">{term.unit || 'dimensionless'}</strong></span>
                <span>Data Type: <strong className="text-slate-800 dark:text-slate-200">{term.provenance}</strong></span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setShowHelp(false)}
                className="px-3 py-1.5 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-md text-xs font-medium hover:bg-slate-800 dark:hover:bg-slate-200 transition-colors"
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
