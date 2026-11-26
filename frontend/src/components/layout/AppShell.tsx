import React, { useState, useEffect, useCallback } from 'react';
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
  X,
  Building2,
  Plus,
  LogOut,
  Loader2
} from 'lucide-react';
import {
  api,
  getActiveProjectId,
  setActiveProjectId,
  clearUserClientCaches,
  type SourceItem,
  type SystemSettings,
  type DeyeStatusResponse,
  type AuthMeResponse,
  type ProjectSummary
} from '../../lib/api';
import { AuthGate } from '../auth/AuthGate';
import type { ViewMode } from '../../lib/terminology';
import { formatDateMMDDYYYY } from '../../lib/formatters';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', subtitle: 'Live & daily summary', icon: LayoutDashboard },
  { path: '/solar', label: 'Solar Intelligence', subtitle: 'PV yield & weather', icon: Sun },
  { path: '/energy', label: 'Energy & Demand', subtitle: 'Balance, grid & battery', icon: Zap },
  { path: '/billing', label: 'Bill Intelligence', subtitle: 'TEI rates & forecast', icon: ReceiptText },
  { path: '/trends', label: 'Trends & History', subtitle: 'Comparisons & anomalies', icon: BarChart3 },
  { path: '/diagnostics', label: 'Diagnostics', subtitle: 'Signal & gap quality', icon: Activity },
  { path: '/scenarios', label: 'What-If & Upgrades', subtitle: 'Sizing & ROI models', icon: Sliders },
  { path: '/analyst', label: 'Energy Analyst', subtitle: 'System reports', icon: BookOpen },
  { path: '/library', label: 'Data Library & Cloud', subtitle: 'CSV/Excel & Deye sync', icon: Database },
  { path: '/settings', label: 'System Settings', subtitle: 'Hardware & thresholds', icon: Settings }
];

export const AppShell: React.FC = () => {
  const [authState, setAuthState] = useState<AuthMeResponse | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);
  const [authBanner, setAuthBanner] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string>(() => getActiveProjectId());
  const [creatingProject, setCreatingProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateProject, setShowCreateProject] = useState(false);

  const [activeDatasetId, setActiveDatasetId] = useState<string>(() => {
    return localStorage.getItem('solarscope_dataset_id') || 'all';
  });
  const [viewMode, setViewMode] = useState<ViewMode>('simple');
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [sysSettings, setSysSettings] = useState<SystemSettings | null>(null);
  const [deyeStatus, setDeyeStatus] = useState<DeyeStatusResponse | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isDark, setIsDark] = useState<boolean>(() => {
    return localStorage.getItem('solarscope_theme') === 'dark';
  });
  const navigate = useNavigate();
  const location = useLocation();

  const loadAuthState = useCallback(async () => {
    try {
      const me = await api.getAuthMe();
      setAuthState(me);
      setProjects(me.projects || []);
      const storedPid = getActiveProjectId();
      const validIds = new Set((me.projects || []).map((p) => p.id));
      let resolvedPid = me.active_project_id || '';
      if (storedPid && validIds.has(storedPid)) {
        resolvedPid = storedPid;
      } else if (me.projects && me.projects.length > 0 && (!resolvedPid || !validIds.has(resolvedPid))) {
        resolvedPid = me.projects[0].id;
      }
      if (resolvedPid && resolvedPid !== storedPid) {
        setActiveProjectId(resolvedPid, false);
      }
      setCurrentProjectId(resolvedPid);
      setAuthBanner(null);
    } catch {
      setAuthState({ authenticated: true, auth_required: false, user: null, projects: [], active_project_id: null });
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAuthState();
    const onAuthChanged = () => loadAuthState();
    const onAuthRequired = () => {
      setAuthBanner('Your session expired. Sign in to access this workspace.');
      setAuthState((prev) => (prev ? { ...prev, authenticated: false, auth_required: true } : prev));
    };
    window.addEventListener('solarscope:auth-changed', onAuthChanged);
    window.addEventListener('solarscope:auth-required', onAuthRequired);
    return () => {
      window.removeEventListener('solarscope:auth-changed', onAuthChanged);
      window.removeEventListener('solarscope:auth-required', onAuthRequired);
    };
  }, [loadAuthState]);

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

  const authGateActive = Boolean(authState?.auth_required && !authState?.authenticated);

  const loadWorkspaceData = useCallback(() => {
    if (authLoading || authGateActive) return;
    api.listSources()
      .then((data) => {
        setSources(data);
        setActiveDatasetId((prev) => {
          if (data.length === 0) {
            try {
              localStorage.removeItem('solarscope_dataset_id');
            } catch {}
            return 'all';
          }
          if (prev !== 'all' && !data.some((s) => s.id === prev)) {
            return 'all';
          }
          return prev;
        });
      })
      .catch(() => {});
    api.getSettings().then(setSysSettings).catch(() => {});
    api.getDeyeStatus().then(setDeyeStatus).catch(() => {});
  }, [authLoading, authGateActive]);

  useEffect(() => {
    loadWorkspaceData();
    const onSources = () => {
      if (authLoading || authGateActive) return;
      api.listSources().then(setSources).catch(() => {});
    };
    const onMeta = () => {
      if (authLoading || authGateActive) return;
      api.getSettings().then(setSysSettings).catch(() => {});
      api.getDeyeStatus().then(setDeyeStatus).catch(() => {});
    };
    const onProjectChanged = () => {
      setCurrentProjectId(getActiveProjectId());
      setActiveDatasetId('all');
      loadWorkspaceData();
    };
    window.addEventListener('solarscope:sources-updated', onSources);
    window.addEventListener('solarscope:settings-updated', onMeta);
    window.addEventListener('solarscope:deye-updated', onMeta);
    window.addEventListener('solarscope:project-changed', onProjectChanged);
    return () => {
      window.removeEventListener('solarscope:sources-updated', onSources);
      window.removeEventListener('solarscope:settings-updated', onMeta);
      window.removeEventListener('solarscope:deye-updated', onMeta);
      window.removeEventListener('solarscope:project-changed', onProjectChanged);
    };
  }, [authLoading, authGateActive, loadWorkspaceData]);

  const handleSwitchProject = (nextId: string) => {
    if (!nextId || nextId === currentProjectId) return;
    setActiveProjectId(nextId, true);
    setCurrentProjectId(nextId);
    setActiveDatasetId('all');
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim() || creatingProject) return;
    setCreatingProject(true);
    try {
      const res = await api.createProject({ name: newProjectName.trim(), installation_type: 'residential' });
      const created = res.project;
      setProjects((prev) => [...prev, created]);
      setCurrentProjectId(created.id);
      setNewProjectName('');
      setShowCreateProject(false);
    } catch {} finally {
      setCreatingProject(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      clearUserClientCaches(false);
    }
    loadAuthState();
  };

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

  if (authLoading) {
    return (
      <div className="min-h-dvh bg-slate-50 dark:bg-slate-950 flex items-center justify-center text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2 text-amber-600" />
        <span className="text-xs font-medium">Loading household workspace...</span>
      </div>
    );
  }

  if (authGateActive) {
    return (
      <AuthGate
        bannerMessage={authBanner}
        onAuthenticated={(res) => {
          setAuthState({
            ...res,
            authenticated: true,
            auth_required: true
          });
          setProjects(res.projects || []);
          const nextPid = res.active_project_id || res.projects?.[0]?.id || '';
          if (nextPid) {
            setActiveProjectId(nextPid, true);
            setCurrentProjectId(nextPid);
          }
          setAuthBanner(null);
        }}
      />
    );
  }

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
              title={item.subtitle}
              onClick={() => isMobileDrawer && setMobileNavOpen(false)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition-all duration-150 active:scale-[0.98] ${
                isActive
                  ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <Icon className={`h-4 w-4 shrink-0 transition-transform duration-150 ${isActive ? 'text-amber-600 scale-105' : 'text-slate-400'}`} />
              <div className="min-w-0">
                <div className="truncate">{item.label}</div>
                <div className="text-[10px] font-normal text-slate-400 dark:text-slate-500 truncate">{item.subtitle}</div>
              </div>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-2.5 shrink-0">
        {projects.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              <span className="flex items-center gap-1">
                <Building2 className="h-3 w-3" />
                Installation
              </span>
              <button
                type="button"
                onClick={() => setShowCreateProject((prev) => !prev)}
                className="text-amber-600 hover:text-amber-700 inline-flex items-center gap-0.5 font-medium"
              >
                <Plus className="h-3 w-3" />
                New
              </button>
            </div>
            <select
              aria-label="Active Solar Installation"
              value={currentProjectId || projects[0]?.id || ''}
              onChange={(e) => handleSwitchProject(e.target.value)}
              className="w-full px-2 py-1.5 text-xs rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:outline-none"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {showCreateProject && (
              <form onSubmit={handleCreateProject} className="flex items-center gap-1 pt-0.5">
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="Home or Site Name"
                  className="flex-1 min-w-0 px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"
                />
                <button
                  type="submit"
                  disabled={creatingProject || !newProjectName.trim()}
                  className="px-2 py-1 text-[11px] font-medium rounded bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 disabled:opacity-50"
                >
                  Add
                </button>
              </form>
            )}
          </div>
        )}

        <div className="flex items-center justify-between gap-2 pt-0.5">
          <button
            type="button"
            onClick={() => setIsDark(!isDark)}
            className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors py-1"
          >
            {isDark ? <SunMedium className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span>{isDark ? 'Light' : 'Dark'}</span>
          </button>

          {authState?.authenticated && !authState?.is_local_mode && (
            <button
              type="button"
              onClick={handleLogout}
              title={authState.user?.email || 'Sign Out'}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400 transition-colors py-1"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          )}
        </div>
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
          <div className="flex flex-1 items-center gap-2 sm:gap-2.5 text-xs min-w-0">
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
            <span className="text-slate-600 dark:text-slate-300 font-medium hidden sm:inline truncate">
              {sysSettings?.station_name?.trim() || 'Station Not Set'}
            </span>
            {deyeStatus?.is_demo ? (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                <span className="hidden min-[380px]:inline">Demo</span>
              </span>
            ) : deyeStatus?.is_configured ? (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span className="hidden min-[380px]:inline">Online</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                <span className="hidden min-[380px]:inline">Offline</span>
              </span>
            )}
            {sysSettings && sysSettings.pv_capacity_kwp > 0 && (
              <span className="text-slate-400 text-[11px] hidden lg:inline shrink-0">
                {sysSettings.pv_capacity_kwp.toFixed(1)} kWp
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            <div className="flex items-center gap-1.5 sm:gap-2 bg-slate-100 dark:bg-slate-800/80 px-2 sm:px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 max-w-[132px] sm:max-w-[260px]">
              <Calendar className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span className="text-xs text-slate-500 font-medium hidden md:inline shrink-0">Scope:</span>
              <select
                aria-label="Dataset Scope"
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
