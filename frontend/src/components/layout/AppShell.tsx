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
  Calendar,
  Menu,
  X
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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isDark, setIsDark] = useState<boolean>(() => {
    return localStorage.getItem('solarscope_theme') === 'dark';
  });
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileNavOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [mobileNavOpen]);

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

  const currentPageLabel = NAV_ITEMS.find((n) => n.path === location.pathname)?.label || 'Energy Intelligence';

  const renderSidebarContent = (isMobileDrawer = false) => (
    <>
      <div className="h-14 px-4 flex items-center justify-between border-b border-slate-200 dark:border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-md bg-amber-600 flex items-center justify-center text-white">
            <Sun className="h-4 w-4" />
          </div>
          <span className="font-semibold text-sm tracking-tight">SolarScope</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">v1.2</span>
          {isMobileDrawer && (
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close navigation"
              className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => isMobileDrawer && setMobileNavOpen(false)}
              className={`flex items-center gap-2.5 px-3 py-2.5 md:py-2 rounded-md text-xs font-medium transition-all duration-150 active:scale-[0.98] ${
                isActive
                  ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <Icon className={`h-4 w-4 shrink-0 transition-transform duration-150 ${isActive ? 'text-amber-600 scale-105' : 'text-slate-400'}`} />
              <span className="truncate">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
        <button
          type="button"
          onClick={() => setIsDark(!isDark)}
          className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors py-1"
        >
          {isDark ? <SunMedium className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
      </div>
    </>
  );

  return (
    <div className="flex h-dvh bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 overflow-hidden font-sans">
      <aside className="hidden md:flex w-60 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex-col shrink-0 z-20">
        {renderSidebarContent(false)}
      </aside>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="relative z-10 w-72 max-w-[85vw] bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shadow-2xl h-full">
            {renderSidebarContent(true)}
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="min-h-14 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between gap-2 px-3 sm:px-6 py-2 shrink-0 z-10">
          <div className="flex items-center gap-2 sm:gap-2.5 text-xs min-w-0">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              aria-label="Open navigation"
              className="md:hidden p-1.5 -ml-1 rounded-md text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
              {currentPageLabel}
            </span>
            <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">/</span>
            <span className="text-slate-600 dark:text-slate-300 font-medium hidden sm:inline truncate">Mam Micah</span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="hidden min-[380px]:inline">Online</span>
            </span>
            <span className="text-slate-400 text-[11px] hidden lg:inline shrink-0">6.2 kWp</span>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            <div className="flex items-center gap-1.5 sm:gap-2 bg-slate-100 dark:bg-slate-800/80 px-2 sm:px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 max-w-[138px] sm:max-w-[260px]">
              <Calendar className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span className="text-xs text-slate-500 font-medium hidden md:inline shrink-0">Scope:</span>
              <select
                value={activeDatasetId || 'all'}
                onChange={(e) => setActiveDatasetId(e.target.value)}
                className="text-xs bg-transparent text-slate-800 dark:text-slate-200 font-medium focus:outline-none cursor-pointer pr-1 w-full min-w-0 truncate"
              >
                <option value="all" className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200">
                  All Dates ({sources.filter((s) => s.is_included === 1).length}d)
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
              type="button"
              onClick={() => navigate('/library?tab=preview')}
              className="text-xs bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 font-medium px-2.5 sm:px-3 py-1.5 rounded-md transition-colors shadow-xs shrink-0"
            >
              <span className="hidden sm:inline">Import Data</span>
              <span className="sm:hidden">Import</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-5 md:p-6">
          <div key={location.pathname} className="animate-page-enter">
            <Outlet context={{ activeDatasetId, setActiveDatasetId, viewMode, setViewMode }} />
          </div>
        </main>
      </div>
    </div>
  );
};
