import { BrowserRouter, Route, Routes } from "react-router-dom";

import { BoxScorePage } from "@/features/matchups/BoxScorePage";
import { MatchupsPage } from "@/features/matchups/MatchupsPage";
import { HomePage } from "@/features/home/HomePage";
import { PlaceholderPage } from "@/features/placeholder/PlaceholderPage";
import { RecordsPage } from "@/features/records/RecordsPage";
import { StandingsPage } from "@/features/standings/StandingsPage";

import { AppShell } from "./shell/AppShell";
import { SeasonProvider } from "./shell/SeasonContext";

export function App() {
  return (
    <BrowserRouter>
      <SeasonProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="standings" element={<StandingsPage />} />
            <Route path="records" element={<RecordsPage />} />
            <Route path="rivalries" element={<PlaceholderPage title="Rivalries" />} />
            <Route path="managers" element={<PlaceholderPage title="Managers" />} />
            <Route path="players" element={<PlaceholderPage title="Players" />} />
            <Route path="matchups" element={<MatchupsPage />} />
            <Route path="matchups/:matchupId" element={<BoxScorePage />} />
            <Route path="draft" element={<PlaceholderPage title="Draft" />} />
            <Route path="*" element={<PlaceholderPage title="Not found" />} />
          </Route>
        </Routes>
      </SeasonProvider>
    </BrowserRouter>
  );
}
