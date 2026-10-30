import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  Activity,
  Sun,
  BatteryCharging,
  Zap,
  Home,
  Scale,
  AlertTriangle,
  BarChart3,
  Sliders,
  DollarSign,
  FileText,
  Settings,
  SunMedium,
  Moon,
  Database,
  Calendar,
  ChevronDown,
  BookOpen,
  ReceiptText
} from 'lucide-react';
import { api, type SourceItem } from '../../lib/api';
import type { ViewMode } from '../../lib/terminology';
import { HelpGlossaryModal } from '../ui/HelpGlossaryModal';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/library', label: 'Historical Library', icon: Database },
  { path: '/billing', label: 'Bill Intelligence', icon: ReceiptText },
  { path: '/import', label: 'Import Data', icon: UploadCloud },
  { path: '/history', label: 'Daily Summaries', icon: Calendar },
  { path: '/compare', label: 'Compare Periods', icon: Scale },
  { path: '/timeline', label: 'Power Timeline', icon: Activity },
  { path: '/solar', label: 'Solar Production', icon: Sun },
  { path: '/battery', label: 'Battery Performance', icon: BatteryCharging },
  { path: '/grid', label: 'Electricity from TEI', icon: Zap },
  { path: '/consumption', label: 'Home Electricity Use', icon: Home },
  { path: '/balance', label: 'Energy Flow Check', icon: Scale },
  { path: '/anomalies', label: 'Unusual Events', icon: AlertTriangle },
  { path: '/statistics', label: 'Averages & Trends', icon: BarChart3 },
  { path: '/scenarios', label: 'What If? Simulator', icon: Sliders },
  { path: '/finance', label: 'Bills & Savings', icon: DollarSign },
  { path: '/reports', label: 'Reports & Exports', icon: FileText },
  { path: '/settings', label: 'System Settings', icon: Settings }
];

export const AppShell: React.FC = () => {
  const [activeDatasetId, setActiveDatasetId] = useState<string>(() => {
    return localStorage.getItem('solarscope_dataset_id') || 'all';
  });
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    return (localStorage.getItem('solarscope_view_mode') as ViewMode) || 'simple';
  });
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [isDark, setIsDark] = useState<boolean>(() => {
    return localStorage.getItem('solarscope_theme') === 'dark';
  });
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    api.listSources()
      .then((data) => {
        setSources(data);
        if (activeDatasetId !== 'all' && data.length > 0 && !data.some((s) => s.id === activeDatasetId)) {
          setActiveDatasetId('all');
        }
      })
      .catch(() => {});
  }, [location.pathname, activeDatasetId]);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('solarscope_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('solarscope_theme', 'light');
    }
  }, [isDark]);

  useEffect(() => {
    if (activeDatasetId) {
      localStorage.setItem('solarscope_dataset_id', activeDatasetId);
    }
  }, [activeDatasetId]);

  useEffect(() => {
    localStorage.setItem('solarscope_view_mode', viewMode);
  }, [viewMode]);

  const sortedSources = [...sources].sort((a, b) => {
    const dateA = a.start_time ? a.start_time.slice(0, 10) : a.filename;
    const dateB = b.start_time ? b.start_time.slice(0, 10) : b.filename;
    return dateA.localeCompare(dateB);
  });

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 overflow-hidden font-sans">
      <aside className="w-60 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col shrink-0 z-20">
        <div className="h-14 px-4 flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-md bg-solar-600 flex items-center justify-center text-white">
              <Sun className="h-4 w-4" />
            </div>
            <span className="font-semibold text-sm tracking-tight">SolarScope</span>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">v1.0</span>
        </div>

        <div className="p-3 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500 font-medium flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-solar-600" />
              <span>Analysis Scope</span>
            </span>
          </div>

          <div className="relative">
            <select
              value={activeDatasetId || 'all'}
              onChange={(e) => setActiveDatasetId(e.target.value)}
              className="w-full text-xs bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 pl-2.5 pr-7 py-2 rounded-lg border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-1 focus:ring-amber-500 font-medium cursor-pointer truncate shadow-sm appearance-none"
            >
              <option value="all">
                All Dates ({sortedSources.filter((s) => s.is_included === 1).length} days combined)
              </option>
              {sortedSources.length > 0 && (
                <optgroup label="Individual Observation Days">
                  {sortedSources.map((s) => {
                    const dateLabel = s.start_time ? s.start_time.slice(0, 10) : s.filename;
                    return (
                      <option key={s.id} value={s.id}>
                        {dateLabel} ({s.filename})
                      </option>
                    );
                  })}
                </optgroup>
              )}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-2.5 pointer-events-none" />
          </div>

          <div className="flex items-center justify-between text-[10px] text-slate-400 pt-0.5">
            <span>{(!activeDatasetId || activeDatasetId === 'all') ? 'Full Portfolio Applied' : 'Single Day Active'}</span>
            <span className="font-mono">{sortedSources.reduce((sum, s) => sum + (s.total_rows || 0), 0).toLocaleString()} rows</span>
          </div>
        </div>

        <div className="p-2 border-b border-slate-200 dark:border-slate-800">
          <button
            onClick={() => setIsHelpModalOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
          >
            <BookOpen className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
            <span className="truncate">Help & Glossary</span>
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-solar-600' : 'text-slate-400'}`} />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <button
            onClick={() => setIsDark(!isDark)}
            className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
          >
            {isDark ? <SunMedium className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between px-6 shrink-0 z-10">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {NAV_ITEMS.find(n => n.path === location.pathname)?.label || 'Analytics'}
            </span>
            <span className="text-slate-300 dark:text-slate-700">/</span>
            <span className="text-slate-500">Local-First Energy Telemetry</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700">
              <button
                onClick={() => setViewMode('simple')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  viewMode === 'simple'
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm font-semibold'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                Simple View
              </button>
              <button
                onClick={() => setViewMode('detailed')}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  viewMode === 'detailed'
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm font-semibold'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                Detailed View
              </button>
            </div>

            <button
              onClick={() => setIsHelpModalOpen(true)}
              title="Help and Glossary"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
              <span>Help & Glossary</span>
            </button>

            <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700">
              <Calendar className="w-3.5 h-3.5 text-solar-600 shrink-0" />
              <span className="text-xs text-slate-500 font-medium hidden sm:inline">Scope:</span>
              <select
                value={activeDatasetId || 'all'}
                onChange={(e) => setActiveDatasetId(e.target.value)}
                className="text-xs bg-transparent text-slate-800 dark:text-slate-200 font-medium focus:outline-none cursor-pointer pr-1"
              >
                <option value="all" className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                  All Dates ({sources.filter((s) => s.is_included === 1).length} days combined)
                </option>
                {sources.length > 0 && (
                  <optgroup label="Individual Observation Days" className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                    {sources.map((s) => {
                      const dateLabel = s.start_time ? s.start_time.slice(0, 10) : s.filename;
                      return (
                        <option key={s.id} value={s.id} className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                          {dateLabel} ({s.filename})
                        </option>
                      );
                    })}
                  </optgroup>
                )}
              </select>
            </div>

            <button
              onClick={() => navigate('/import')}
              className="text-xs bg-solar-600 hover:bg-solar-700 text-white font-medium px-3 py-1.5 rounded-md transition-colors"
            >
              Import Data
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet context={{ activeDatasetId, setActiveDatasetId, viewMode, setViewMode }} />
        </main>

        <HelpGlossaryModal
          isOpen={isHelpModalOpen}
          onClose={() => setIsHelpModalOpen(false)}
        />
      </div>
    </div>
  );
};
