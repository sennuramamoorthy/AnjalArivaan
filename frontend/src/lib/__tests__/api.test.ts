/**
 * NOTE: The canonical HTTP-client tests live in `src/lib/api.test.ts`.
 * This file exists only because vitest's glob (`src/**​/*.test.ts`)
 * picks it up; the real assertions are in the parent directory.
 */
import { describe, it } from "vitest";

describe.skip("api (see src/lib/api.test.ts for canonical tests)", () => {
  it("placeholder", () => {});
});
