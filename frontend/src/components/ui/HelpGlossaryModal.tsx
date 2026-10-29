import React, { useState } from 'react';
import { Search, X, BookOpen, FolderSync, ShieldCheck } from 'lucide-react';
import { GLOSSARY } from '../../lib/terminology';

interface HelpGlossaryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpGlossaryModal: React.FC<HelpGlossaryModalProps> = ({
  isOpen,
  onClose
}) => {
  const [activeTab, setActiveTab] = useState<'glossary' | 'guide'>('glossary');
  const [searchQuery, setSearchQuery] = useState('');

  if (!isOpen) return null;

  const terms = Object.values(GLOSSARY);
  const filteredTerms = terms.filter(t => 
    t.simpleLabel.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.technicalLabel.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.simpleExplanation.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-lg">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                SolarScope Help & Plain-Language Guide
              </h2>
              <p className="text-xs text-slate-500">
                Simple everyday explanations of solar terms, multi-file uploads, and energy calculations.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 px-5">
          <button
            onClick={() => setActiveTab('glossary')}
            className={`py-3 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'glossary'
                ? 'border-amber-500 text-amber-700 dark:text-amber-400'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            Everyday Glossary ({terms.length} terms)
          </button>
          <button
            onClick={() => setActiveTab('guide')}
            className={`py-3 px-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === 'guide'
                ? 'border-amber-500 text-amber-700 dark:text-amber-400'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            Multi-File & Upload Guide
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === 'glossary' && (
            <div className="space-y-4">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search any solar, battery, grid, or measurement term..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full text-xs bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 pl-9 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {filteredTerms.map((t) => (
                  <div
                    key={t.id}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div>
                        <div className="text-xs font-semibold text-slate-900 dark:text-white">
                          {t.simpleLabel}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400">
                          {t.technicalLabel}
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                        {t.provenance}
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      {t.simpleExplanation}
                    </p>

                    {t.formula && (
                      <div className="text-[10px] font-mono bg-slate-50 dark:bg-slate-800/80 p-1.5 rounded text-slate-700 dark:text-slate-300">
                        {t.formula}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'guide' && (
            <div className="space-y-4 text-xs">
              <div className="p-4 bg-amber-50/50 dark:bg-amber-950/20 rounded-xl border border-amber-200/60 dark:border-amber-900/40 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-amber-900 dark:text-amber-200">
                  <FolderSync className="w-4 h-4 text-amber-600" />
                  <span>How to Import Multiple Excel and CSV Files</span>
                </div>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                  SolarScope allows you to drag and drop multiple daily or monthly inverter exports at once. You do not need to combine spreadsheets manually.
                </p>
                <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-400 pt-1">
                  <li><strong>Instant SHA-256 Check:</strong> Identical files are recognized instantly to prevent counting the same electricity twice.</li>
                  <li><strong>Overlap Resolution:</strong> If two files cover the same date, SolarScope warns you and lets you select whether to keep existing data or replace it.</li>
                  <li><strong>All Dates vs Single Day:</strong> Use the Scope dropdown in the header to view your entire multi-day history or zoom in on one day.</li>
                </ul>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                  <ShieldCheck className="w-4 h-4 text-teal-600" />
                  <span>Understanding the 12-Hour Clock Format</span>
                </div>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                  All times across SolarScope are standardized into familiar 12-hour format:
                </p>
                <div className="grid grid-cols-2 gap-2 font-mono text-[11px] pt-1">
                  <div className="p-2 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">
                    Midnight = <strong>12:00 AM</strong>
                  </div>
                  <div className="p-2 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">
                    Noon = <strong>12:00 PM</strong>
                  </div>
                  <div className="p-2 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">
                    Peak Solar = typically <strong>11:00 AM - 1:30 PM</strong>
                  </div>
                  <div className="p-2 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">
                    Evening Peak = typically <strong>6:00 PM - 9:00 PM</strong>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-lg text-xs font-medium hover:bg-slate-800 dark:hover:bg-slate-200 transition-colors"
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  );
};
