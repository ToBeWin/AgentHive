import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  activatePrototypeMode,
  clearPrototypeMode,
  getStoredPrototypeMode,
  isPrototypeModeAvailable,
} from "./runtimeMode";

const PROTOTYPE_MODE_KEY = "agenthive.runtime.prototype_mode";

describe("isPrototypeModeAvailable", () => {
  it("returns true in the vitest dev environment by default", () => {
    expect(isPrototypeModeAvailable()).toBe(true);
  });

  it("returns false when the DEV env flag is stubbed to false", () => {
    vi.stubEnv("DEV", false);
    expect(isPrototypeModeAvailable()).toBe(false);
    vi.unstubAllEnvs();
  });
});

describe("getStoredPrototypeMode", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns false when storage is empty", () => {
    expect(getStoredPrototypeMode()).toBe(false);
  });

  it("returns true when prototype mode is enabled in storage", () => {
    window.sessionStorage.setItem(PROTOTYPE_MODE_KEY, "enabled");
    expect(getStoredPrototypeMode()).toBe(true);
  });

  it("returns false for a non-'enabled' storage value", () => {
    window.sessionStorage.setItem(PROTOTYPE_MODE_KEY, "true");
    expect(getStoredPrototypeMode()).toBe(false);
  });

  it("returns false when not in dev mode even if storage is set", () => {
    window.sessionStorage.setItem(PROTOTYPE_MODE_KEY, "enabled");
    vi.stubEnv("DEV", false);
    expect(getStoredPrototypeMode()).toBe(false);
  });
});

describe("activatePrototypeMode", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns true and persists the flag in storage when in dev mode", () => {
    expect(activatePrototypeMode()).toBe(true);
    expect(window.sessionStorage.getItem(PROTOTYPE_MODE_KEY)).toBe("enabled");
  });

  it("returns false and leaves storage untouched when not in dev mode", () => {
    vi.stubEnv("DEV", false);
    expect(activatePrototypeMode()).toBe(false);
    expect(window.sessionStorage.getItem(PROTOTYPE_MODE_KEY)).toBeNull();
  });
});

describe("clearPrototypeMode", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("removes the prototype mode entry from storage", () => {
    window.sessionStorage.setItem(PROTOTYPE_MODE_KEY, "enabled");
    clearPrototypeMode();
    expect(window.sessionStorage.getItem(PROTOTYPE_MODE_KEY)).toBeNull();
  });

  it("does not throw when storage is already empty", () => {
    expect(() => clearPrototypeMode()).not.toThrow();
  });
});
