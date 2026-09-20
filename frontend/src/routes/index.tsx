import { lazy, Suspense, type ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import { Panel } from "@/components/Panel";
import Live from "@/routes/Live";

// Live is bundled with the shell because it is the route the app opens on. Analysis routes are only reached
// after a session has been saved, so they are split out and fetched when first visited.
const Sessions = lazy(() => import("@/routes/Sessions"));
const LapDetail = lazy(() => import("@/routes/LapDetail"));
const Compare = lazy(() => import("@/routes/Compare"));
const NotFound = lazy(() => import("@/routes/NotFound"));

function Loading() {
  return (
    <Panel title="Loading">
      <p className="text-text-3">Fetching the view.</p>
    </Panel>
  );
}

function deferred(Component: ComponentType) {
  return (
    <Suspense fallback={<Loading />}>
      <Component />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Live /> },
      { path: "sessions", element: deferred(Sessions) },
      { path: "sessions/:sessionId/laps/:lapNumber", element: deferred(LapDetail) },
      { path: "compare", element: deferred(Compare) },
      { path: "*", element: deferred(NotFound) },
    ],
  },
]);
