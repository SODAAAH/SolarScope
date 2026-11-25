import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";

const OverviewPage = lazy(() => import("./pages/OverviewPage").then((m) => ({ default: m.OverviewPage })));
const SolarPage = lazy(() => import("./pages/SolarPage").then((m) => ({ default: m.SolarPage })));
const EnergyPage = lazy(() => import("./pages/EnergyPage").then((m) => ({ default: m.EnergyPage })));
const BillIntelligencePage = lazy(() => import("./pages/BillIntelligencePage").then((m) => ({ default: m.BillIntelligencePage })));
const TrendsPage = lazy(() => import("./pages/TrendsPage").then((m) => ({ default: m.TrendsPage })));
const DiagnosticsPage = lazy(() => import("./pages/DiagnosticsPage").then((m) => ({ default: m.DiagnosticsPage })));
const ScenariosPage = lazy(() => import("./pages/ScenariosPage").then((m) => ({ default: m.ScenariosPage })));
const AnalystPage = lazy(() => import("./pages/AnalystPage").then((m) => ({ default: m.AnalystPage })));
const HistoricalLibraryPage = lazy(() => import("./pages/HistoricalLibraryPage").then((m) => ({ default: m.HistoricalLibraryPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));

const PageLoader: React.FC = () => (
  <div className="flex items-center justify-center py-16">
    <div className="h-6 w-6 rounded-full border-2 border-slate-300 dark:border-slate-700 border-t-amber-600 animate-spin" />
  </div>
);

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="solar" element={<SolarPage />} />
            <Route path="energy" element={<EnergyPage />} />
            <Route path="billing" element={<BillIntelligencePage />} />
            <Route path="trends" element={<TrendsPage />} />
            <Route path="diagnostics" element={<DiagnosticsPage />} />
            <Route path="scenarios" element={<ScenariosPage />} />
            <Route path="analyst" element={<AnalystPage />} />
            <Route path="library" element={<HistoricalLibraryPage />} />
            <Route path="settings" element={<SettingsPage />} />

            <Route path="battery" element={<Navigate to="/energy?tab=battery" replace />} />
            <Route path="grid" element={<Navigate to="/energy?tab=grid" replace />} />
            <Route path="consumption" element={<Navigate to="/energy?tab=consumption" replace />} />
            <Route path="timeline" element={<Navigate to="/energy?tab=timeline" replace />} />
            <Route path="history" element={<Navigate to="/trends?tab=summaries" replace />} />
            <Route path="compare" element={<Navigate to="/trends?tab=compare" replace />} />
            <Route path="statistics" element={<Navigate to="/trends?tab=statistics" replace />} />
            <Route path="balance" element={<Navigate to="/diagnostics?tab=balance" replace />} />
            <Route path="anomalies" element={<Navigate to="/diagnostics?tab=anomalies" replace />} />
            <Route path="finance" element={<Navigate to="/scenarios?tab=payback" replace />} />
            <Route path="import" element={<Navigate to="/library?tab=preview" replace />} />
            <Route path="reports" element={<Navigate to="/trends?tab=summaries" replace />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
};

export default App;
