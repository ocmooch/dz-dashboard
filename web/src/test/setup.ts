import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom lacks ResizeObserver, which Recharts' ResponsiveContainer needs. A no-op
// keeps chart wrappers from throwing under test (they render at 0 size, which is fine).
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// Unmount React trees between tests so the jsdom document stays isolated.
afterEach(() => {
  cleanup();
});
