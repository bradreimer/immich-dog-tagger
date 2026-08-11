import { useEffect, useState } from "react";

import { AppShell } from "./components/layout/AppShell";
import { JobQueuePage } from "./features/jobs/JobQueuePage";
import { MetricsPage } from "./features/metrics/MetricsPage";
import { MissionControlPage } from "./features/mission-control/MissionControlPage";
import { ReviewPage } from "./features/review/ReviewPage";

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
    if (path === pathname) {
      return;
    }

    window.history.pushState({}, "", path);
    setPathname(path);
  };

  const page = (() => {
    if (pathname === "/review") {
      return <ReviewPage />;
    }

    if (pathname === "/jobs") {
      return <JobQueuePage />;
    }

    if (pathname === "/metrics") {
      return <MetricsPage />;
    }

    return <MissionControlPage />;
  })();

  return (
    <AppShell currentPath={pathname} onNavigate={navigate}>
      {page}
    </AppShell>
  );
}

export default App;