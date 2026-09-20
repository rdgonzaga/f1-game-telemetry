import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library only unmounts automatically when Vitest runs with globals enabled, and this project
// imports its test helpers explicitly. Without this, a second render finds the first one still there.
afterEach(cleanup);
