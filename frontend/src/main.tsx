import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { LiveSocket } from "@/live/socket";
import { router } from "@/routes";
import "@/styles/theme.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root");

// Started outside React: it lives as long as the page does, and an effect would open it twice under
// StrictMode and again on every hot reload.
new LiveSocket().start();

createRoot(root).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
