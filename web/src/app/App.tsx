import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AboutPage } from "@/features/about/AboutPage";
import { PlayoffsPage } from "@/features/playoffs/PlayoffsPage";
import { DraftPage } from "@/features/draft/DraftPage";
import { HomePage } from "@/features/home/HomePage";
import { VizLabPage } from "@/features/lab/VizLabPage";
import { LeagueHistoryPage } from "@/features/league/LeagueHistoryPage";
import { StoriesPage } from "@/features/league/StoriesPage";
import { BoxScorePage } from "@/features/matchups/BoxScorePage";
import { MatchupsPage } from "@/features/matchups/MatchupsPage";
import { ManagersPage } from "@/features/managers/ManagersPage";
import { ManagerProfilePage } from "@/features/managers/ManagerProfilePage";
import { PlaceholderPage } from "@/features/placeholder/PlaceholderPage";
import { PlayerDetailPage } from "@/features/players/PlayerDetailPage";
import { PlayersPage } from "@/features/players/PlayersPage";
import { RecordsPage } from "@/features/records/RecordsPage";
import { PairwisePage } from "@/features/rivalries/PairwisePage";
import { RivalriesPage } from "@/features/rivalries/RivalriesPage";
import { StandingsPage } from "@/features/standings/StandingsPage";
import { StatsPage } from "@/features/stats/StatsPage";
import { TeamPage } from "@/features/teams/TeamPage";
import { TeamsIndexPage } from "@/features/teams/TeamsIndexPage";

import { AppShell } from "./shell/AppShell";
import { SeasonProvider } from "./shell/SeasonContext";

export function App() {
  return (
    <BrowserRouter>
      <SeasonProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="timeline" element={<LeagueHistoryPage />} />
            {/* Merged: /seasons + /rules now live in one Timeline space. */}
            <Route path="seasons" element={<Navigate to="/timeline" replace />} />
            <Route path="rules" element={<Navigate to="/timeline" replace />} />
            <Route path="standings" element={<StandingsPage />} />
            <Route path="power" element={<Navigate to="/standings?lens=power" replace />} />
            <Route path="playoffs" element={<PlayoffsPage />} />
            <Route path="bracket" element={<Navigate to="/playoffs" replace />} />
            <Route path="records" element={<RecordsPage />} />
            <Route path="stories" element={<StoriesPage />} />
            <Route path="rivalries" element={<RivalriesPage />} />
            <Route path="rivalries/:a/vs/:b" element={<PairwisePage />} />
            <Route path="matchups" element={<MatchupsPage />} />
            <Route path="matchups/:matchupId" element={<BoxScorePage />} />
            <Route path="managers" element={<ManagersPage />} />
            <Route path="managers/:ownerId" element={<ManagerProfilePage />} />
            <Route path="players" element={<PlayersPage />} />
            <Route path="players/:playerId" element={<PlayerDetailPage />} />
            <Route path="stats" element={<StatsPage />} />
            <Route path="teams" element={<TeamsIndexPage />} />
            <Route path="teams/:teamId" element={<TeamPage />} />
            <Route path="draft" element={<DraftPage />} />
            <Route path="lab" element={<VizLabPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<PlaceholderPage title="Not found" />} />
          </Route>
        </Routes>
      </SeasonProvider>
    </BrowserRouter>
  );
}
