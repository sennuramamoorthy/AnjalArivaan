import "@testing-library/jest-dom/vitest";

// Polyfill for Next.js / jsdom quirks if needed
if (typeof window !== "undefined") {
  window.matchMedia =
    window.matchMedia ||
    ((() => ({
      matches: false,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia);
}
