import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { OverviewPage } from "./pages/OverviewPage";
import { HistoricalLibraryPage } from "./pages/HistoricalLibraryPage";
import { ImportPage } from "./pages/ImportPage";
import { DailySummariesPage } from "./pages/DailySummariesPage";
import { ComparePage } from "./pages/ComparePage";
import { TimelinePage } from "./pages/TimelinePage";
import { SolarPage } from "./pages/SolarPage";
import { BatteryPage } from "./pages/BatteryPage";
import { GridPage } from "./pages/GridPage";
import { ConsumptionPage } from "./pages/ConsumptionPage";
import { BalancePage } from "./pages/BalancePage";
import { AnomaliesPage } from "./pages/AnomaliesPage";
import { StatisticsPage } from "./pages/StatisticsPage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { FinancePage } from "./pages/FinancePage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="library" element={<HistoricalLibraryPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="history" element={<DailySummariesPage />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="timeline" element={<TimelinePage />} />
          <Route path="solar" element={<SolarPage />} />
          <Route path="battery" element={<BatteryPage />} />
          <Route path="grid" element={<GridPage />} />
          <Route path="consumption" element={<ConsumptionPage />} />
          <Route path="balance" element={<BalancePage />} />
          <Route path="anomalies" element={<AnomaliesPage />} />
          <Route path="statistics" element={<StatisticsPage />} />
          <Route path="scenarios" element={<ScenariosPage />} />
          <Route path="finance" element={<FinancePage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
