import { vi } from 'vitest';

// The existing suite uses only this small Jest-compatible surface. Keeping the
// alias localized avoids a noisy mechanical rewrite of hundreds of tests.
globalThis.jest = {
  fn: vi.fn,
  spyOn: vi.spyOn,
  restoreAllMocks: vi.restoreAllMocks,
  setTimeout(milliseconds) {
    vi.setConfig({
      testTimeout: milliseconds,
      hookTimeout: milliseconds,
    });
  },
};

