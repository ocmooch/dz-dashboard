import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "@/features/home/HomePage";
import { BoxScorePage } from "@/features/matchups/BoxScorePage";
import { MatchupsPage } from "@/features/matchups/MatchupsPage";
import { PlaceholderPage } from "@/features/placeholder/PlaceholderPage";
import { RecordsPage } from "@/features/records/RecordsPage";
import { PairwisePage } from "@/features/rivalries/PairwisePage";
import { RivalriesPage } from "@/features/rivalries/RivalriesPage";
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
            <Route path="rivalries" element={<RivalriesPage />} />
            <Route path="rivalries/:a/vs/:b" element={<PairwisePage />} />
            <Route path="matchups" element={<MatchupsPage />} />
            <Route path="matchups/:matchupId" element={<BoxScorePage />} />
            <Route path="managers" element={<PlaceholderPage title="Managers" />} />
            {/* Deep-link targets whose full pages land later (P4/P7). */}
            <Route path="managers/:ownerId" element={<PlaceholderPage title="Manager profile" />} />
            <Route path="players" element={<PlaceholderPage title="Players" />} />
            <Route path="players/:playerId" element={<PlaceholderPage title="Player" />} />
            <Route path="draft" element={<PlaceholderPage title="Draft" />} />
            <Route path="*" element={<PlaceholderPage title="Not found" />} />
          </Route>
        </Routes>
      </SeasonProvider>
    </BrowserRouter>
  );
}
