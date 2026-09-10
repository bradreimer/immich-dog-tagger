import { useEffect, useState } from "react";

import { AppShell } from "./components/layout/AppShell";
import { DogInsightsPage } from "./features/dogs/DogInsightsPage";
import { DogsPage } from "./features/dogs/DogsPage";
import { JobQueuePage } from "./features/jobs/JobQueuePage";
import { LibraryPage } from "./features/library/LibraryPage";
import { MetricsPage } from "./features/metrics/MetricsPage";
import { OverviewPage } from "./features/overview/OverviewPage";
import { PhotoLookupPage } from "./features/photo-lookup/PhotoLookupPage";
import { ReviewPage } from "./features/review/ReviewPage";
import { SettingsPage } from "./features/settings/SettingsPage";

function getPathname() {
  return window.location.pathname;
}

function App() {
  const [pathname, setPathname] = useState(getPathname());

  useEffect(() => {
    const onPopState = () => setPathname(getPathname());
    window.addEventListener("popstate", onPopState);

    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (path: string) => {
    // `path` may carry a query string (e.g. Library's "Review these" bridge,
    // issue #289) -- `pathname` state tracks only window.location.pathname,
    // so route matching below must compare against that same bare form.
    const nextPathname = path.split("?")[0];

    if (path === pathname) {
      return;
    }

    window.history.pushState({}, "", path);
    setPathname(nextPathname);
  };

  const page = (() => {
    if (pathname === "/review") {
      return <ReviewPage onNavigate={navigate} />;
    }

    const dogInsightsMatch = pathname.match(/^\/dogs\/(\d+)\/insights$/);
    if (dogInsightsMatch) {
      return (
        <DogInsightsPage
          dogId={Number(dogInsightsMatch[1])}
          onNavigate={navigate}
        />
      );
    }

    if (pathname === "/dogs") {
      return <DogsPage onNavigate={navigate} />;
    }

    if (pathname === "/library") {
      return <LibraryPage onNavigate={navigate} />;
    }

    if (pathname === "/photo-lookup") {
      return <PhotoLookupPage />;
    }

    if (pathname === "/jobs") {
      return <JobQueuePage />;
    }

    if (pathname === "/metrics") {
      return <MetricsPage onNavigate={navigate} />;
    }

    if (pathname === "/settings") {
      return <SettingsPage />;
    }

    return <OverviewPage />;
  })();

  return (
    <AppShell currentPath={pathname} onNavigate={navigate}>
      {page}
    </AppShell>
  );
}

export default App;