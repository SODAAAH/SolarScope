import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Sun,
  Zap,
  ReceiptText,
  BarChart3,
  Activity,
  Sliders,
  BookOpen,
  Database,
  Settings,
  SunMedium,
  Moon,
  Calendar
} from 'lucide-react';
import { api, type SourceItem } from '../../lib/api';
import type { ViewMode } from '../../lib/terminology';
import { formatDateMMDDYYYY } from '../../lib/formatters';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/solar', label: 'Solar Intelligence', icon: Sun },
  { path: '/energy', label: 'Energy & Demand', icon: Zap },
  { path: '/billing', label: 'Bill Intelligence', icon: ReceiptText },
  { path: '/trends', label: 'Trends & History', icon: BarChart3 },
  { path: '/diagnostics', label: 'Diagnostics', icon: Activity },
  { path: '/scenarios', label: 'What-If & Upgrades', icon: Sliders },
  { path: '/analyst', label: 'Energy Analyst', icon: BookOpen },
  { path: '/library', label: 'Data Library & Cloud', icon: Database },
  { path: '/settings', label: 'System Settings', icon: Settings }
];

export const AppShell: React.FC = () => {
  const [activeDatasetId, setActiveDatasetId] = useState<string>(() => {
    return localStorage.getItem('solarscope_dataset_id') || 'all';
  });
  const [viewMode, setViewMode] = useState<ViewMode>('simple');
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [isDark, setIsDark] = useState<boolean>(() => {
    return localStorage.getItem('solarscope_theme') === 'dark';
  });
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
            <div className="h-7 w-7 rounded-md bg-amber-600 flex items-center justify-center text-white">
              <Sun className="h-4 w-4" />
            </div>
            <span className="font-semibold text-sm tracking-tight">SolarScope</span>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">v1.2</span>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
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
                <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-amber-600' : 'text-slate-400'}`} />
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
              {NAV_ITEMS.find(n => n.path === location.pathname)?.label || 'Energy Intelligence'}
            </span>
            <span className="text-slate-300 dark:text-slate-700">/</span>
            <span className="text-slate-500">Local-First Energy Telemetry</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700">
              <Calendar className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span className="text-xs text-slate-500 font-medium hidden sm:inline">Scope:</span>
              <select
                value={activeDatasetId || 'all'}
                onChange={(e) => setActiveDatasetId(e.target.value)}
                className="text-xs bg-transparent text-slate-800 dark:text-slate-200 font-medium focus:outline-none cursor-pointer pr-1"
              >
                <option value="all" className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                  All Dates ({sources.filter((s) => s.is_included === 1).length} days combined)
                </option>
                {sortedSources.length > 0 && (
                  <optgroup label="Individual Observation Days" className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                    {sortedSources.map((s) => {
                      const dateLabel = s.start_time ? formatDateMMDDYYYY(s.start_time) : s.filename;
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
              onClick={() => navigate('/library?tab=preview')}
              className="text-xs bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 font-medium px-3 py-1.5 rounded-md transition-colors shadow-xs"
            >
              Import Data
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet context={{ activeDatasetId, setActiveDatasetId, viewMode, setViewMode }} />
        </main>


      </div>
    </div>
  );
};
