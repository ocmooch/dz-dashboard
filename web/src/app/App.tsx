import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "@/features/home/HomePage";
import { DraftPage } from "@/features/draft/DraftPage";
import { BoxScorePage } from "@/features/matchups/BoxScorePage";
import { MatchupsPage } from "@/features/matchups/MatchupsPage";
import { PlaceholderPage } from "@/features/placeholder/PlaceholderPage";
import { PlayerDetailPage } from "@/features/players/PlayerDetailPage";
import { PlayersPage } from "@/features/players/PlayersPage";
import { RecordsPage } from "@/features/records/RecordsPage";
import { PairwisePage } from "@/features/rivalries/PairwisePage";
import { RivalriesPage } from "@/features/rivalries/RivalriesPage";
import { StandingsPage } from "@/features/standings/StandingsPage";
import { StatsPage } from "@/features/stats/StatsPage";
import { TeamPage } from "@/features/teams/TeamPage";

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
            {/* Deep-link target whose full page lands later (P4). */}
            <Route path="managers/:ownerId" element={<PlaceholderPage title="Manager profile" />} />
            <Route path="players" element={<PlayersPage />} />
            <Route path="players/:playerId" element={<PlayerDetailPage />} />
            <Route path="stats" element={<StatsPage />} />
            <Route path="teams/:teamId" element={<TeamPage />} />
            <Route path="draft" element={<DraftPage />} />
            <Route path="*" element={<PlaceholderPage title="Not found" />} />
          </Route>
        </Routes>
      </SeasonProvider>
    </BrowserRouter>
  );
}
