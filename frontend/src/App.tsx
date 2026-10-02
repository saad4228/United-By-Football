import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router";
import { Layout } from "./components/layout/Shell";
import { HomePage } from "./pages/HomePage";
import { MatchPage } from "./pages/MatchPage";

// Home and match pages are the hot path; everything else is split out.
const directory = () => import("./pages/DirectoryPages");
const SchedulePage = lazy(() => import("./pages/SchedulePage").then((m) => ({ default: m.SchedulePage })));
const CompetitionsPage = lazy(() => directory().then((m) => ({ default: m.CompetitionsPage })));
const CompetitionPage = lazy(() => directory().then((m) => ({ default: m.CompetitionPage })));
const TeamsPage = lazy(() => directory().then((m) => ({ default: m.TeamsPage })));
const TeamPage = lazy(() => directory().then((m) => ({ default: m.TeamPage })));
const SearchPage = lazy(() => directory().then((m) => ({ default: m.SearchPage })));
const NotFoundPage = lazy(() => directory().then((m) => ({ default: m.NotFoundPage })));
const AboutPage = lazy(() => directory().then((m) => ({ default: m.AboutPage })));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const MyTeamsPage = lazy(() => import("./pages/MyTeamsPage").then((m) => ({ default: m.MyTeamsPage })));
const SecretPage = lazy(() => import("./pages/SecretPage").then((m) => ({ default: m.SecretPage })));

const fallback = <div className="container-x min-h-[60vh] pt-20" aria-busy="true" />;

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <Suspense fallback={fallback}>
              <Layout />
            </Suspense>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="matches" element={<SchedulePage />} />
          <Route path="live" element={<SchedulePage key="live" preset="live" />} />
          <Route path="upcoming" element={<SchedulePage key="upcoming" preset="upcoming" />} />
          <Route path="match/:slug" element={<MatchPage />} />
          <Route path="competitions" element={<CompetitionsPage />} />
          <Route path="competition/:slug" element={<CompetitionPage />} />
          <Route path="teams" element={<TeamsPage />} />
          <Route path="team/:slug" element={<TeamPage />} />
          <Route path="my-teams" element={<MyTeamsPage />} />
          {/* Hidden: renders "not found" until the phrase is typed into search. */}
          <Route path="vault" element={<SecretPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="admin" element={<AdminPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
