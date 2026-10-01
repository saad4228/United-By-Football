import "@fontsource/barlow/latin-400.css";
import "@fontsource/barlow/latin-500.css";
import "@fontsource/barlow/latin-600.css";
import "@fontsource/barlow/latin-700.css";
import "@fontsource/barlow-condensed/latin-700.css";
import "@fontsource/barlow-condensed/latin-800.css";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LazyMotion, MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { CountryProvider } from "./lib/country";
import { initialLanguage, loadLanguage } from "./lib/i18n";
import { MyTeamsProvider } from "./lib/myteams";
import { initialTimeZone, PrefsProvider } from "./lib/prefs";
import { setTimeZoneSetting } from "./lib/time";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      refetchOnWindowFocus: true,
      refetchIntervalInBackground: false,
      retry: 2,
    },
  },
});

// Apply the saved language and time zone before the first render, so nothing flashes in English.
const zone = initialTimeZone();
setTimeZoneSetting(zone);
await loadLanguage(initialLanguage()).catch(() => loadLanguage("en"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        {/* Animation features load after first paint; components use the lightweight `m`. */}
        <LazyMotion features={() => import("./lib/motion-features").then((r) => r.default)} strict>
          <PrefsProvider initialZone={zone}>
            <CountryProvider>
              <MyTeamsProvider>
                <App />
              </MyTeamsProvider>
            </CountryProvider>
          </PrefsProvider>
        </LazyMotion>
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
