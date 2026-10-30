import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { OverviewPage } from "./pages/OverviewPage";
import { SolarPage } from "./pages/SolarPage";
import { EnergyPage } from "./pages/EnergyPage";
import { BillIntelligencePage } from "./pages/BillIntelligencePage";
import { TrendsPage } from "./pages/TrendsPage";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { AnalystPage } from "./pages/AnalystPage";
import { HistoricalLibraryPage } from "./pages/HistoricalLibraryPage";
import { SettingsPage } from "./pages/SettingsPage";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
};

export default App;
