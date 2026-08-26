import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getStoredLocale,
  isLocale,
  LOCALE_STORAGE_KEY,
  loadMessages,
  messages,
  saveLocale,
  setMessagesForLocale,
  t,
} from "./i18n";
import { defaultMessages } from "./i18n/messages";
import type { Messages } from "./i18n/messages/types";

function setNavigatorLanguage(language: string) {
  Object.defineProperty(window.navigator, "language", {
    value: language,
    configurable: true,
  });
}

function restoreNavigatorLanguage() {
  // jsdom defaults to en-US; redefine so later tests start from a known state.
  setNavigatorLanguage("en-US");
}

describe("t", () => {
  it("returns the English message for a known key", async () => {
    await loadMessages("en-US");
    expect(t("en-US", "overview")).toBe("Overview");
    expect(t("en-US", "agents")).toBe("Agents");
  });

  it("returns the Chinese message for a known key after loading", async () => {
    await loadMessages("zh-CN");
    expect(t("zh-CN", "overview")).toBe("概览");
    expect(t("zh-CN", "agents")).toBe("智能体");
  });

  it("returns the key itself when the key is missing in the locale", () => {
    expect(t("en-US", "nonexistent.key")).toBe("nonexistent.key");
    expect(t("zh-CN", "nonexistent.key")).toBe("nonexistent.key");
  });

  it("returns the key for an empty-string locale lookup", () => {
    expect(t("en-US", "")).toBe("");
  });
});

describe("isLocale", () => {
  it("returns true for supported locale strings", () => {
    expect(isLocale("en-US")).toBe(true);
    expect(isLocale("zh-CN")).toBe(true);
  });

  it("returns false for unsupported locale strings", () => {
    expect(isLocale("en-GB")).toBe(false);
    expect(isLocale("zh")).toBe(false);
    expect(isLocale("ja-JP")).toBe(false);
    expect(isLocale("en-us")).toBe(false);
  });

  it("returns false for non-string values", () => {
    expect(isLocale(null)).toBe(false);
    expect(isLocale(undefined)).toBe(false);
    expect(isLocale(123)).toBe(false);
    expect(isLocale({ locale: "en-US" })).toBe(false);
    expect(isLocale(["en-US"])).toBe(false);
  });

  it("acts as a type guard that narrows to Locale", () => {
    const value: unknown = "zh-CN";
    if (isLocale(value)) {
      expect(messages[value]).toBeDefined();
    } else {
      throw new Error("expected value to be recognized as a Locale");
    }
  });
});

describe("getStoredLocale", () => {
  beforeEach(() => {
    window.localStorage.clear();
    restoreNavigatorLanguage();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    restoreNavigatorLanguage();
  });

  it("returns the stored locale when it is valid", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "zh-CN");
    expect(getStoredLocale()).toBe("zh-CN");
  });

  it("returns the zh-CN product default when the stored value is not valid", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "fr-FR");
    expect(getStoredLocale()).toBe("zh-CN");
  });

  it("falls back to zh-CN when navigator.language starts with zh and no stored value", () => {
    setNavigatorLanguage("zh-CN");
    expect(getStoredLocale()).toBe("zh-CN");
  });

  it("falls back to zh-CN for a zh-* navigator.language variant", () => {
    setNavigatorLanguage("zh-TW");
    expect(getStoredLocale()).toBe("zh-CN");
  });

  it("uses the zh-CN product default regardless of browser language", () => {
    setNavigatorLanguage("ja-JP");
    expect(getStoredLocale()).toBe("zh-CN");
  });

  it("returns zh-CN when localStorage access throws", () => {
    vi.spyOn(window.localStorage, "getItem").mockImplementation(() => {
      throw new Error("blocked by browser");
    });
    expect(getStoredLocale()).toBe("zh-CN");
  });

  it("prefers the stored locale over the navigator language", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en-US");
    setNavigatorLanguage("zh-CN");
    expect(getStoredLocale()).toBe("en-US");
  });
});

describe("saveLocale", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("persists the locale under the storage key", () => {
    saveLocale("zh-CN");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("zh-CN");
  });

  it("overwrites the previously stored locale", () => {
    saveLocale("zh-CN");
    saveLocale("en-US");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en-US");
  });

  it("does not throw when localStorage.setItem throws", () => {
    vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("blocked by browser");
    });
    expect(() => saveLocale("zh-CN")).not.toThrow();
  });
});

describe("messages", () => {
  it("contains exactly the en-US and zh-CN locales", () => {
    expect(Object.keys(messages).sort()).toEqual(["en-US", "zh-CN"]);
  });

  it("provides non-empty message maps for each locale", () => {
    expect(Object.keys(messages["en-US"]).length).toBeGreaterThan(0);
    expect(Object.keys(messages["zh-CN"]).length).toBeGreaterThan(0);
  });

  it("shares the same set of keys across locales", () => {
    const enKeys = Object.keys(messages["en-US"]).sort();
    const zhKeys = Object.keys(messages["zh-CN"]).sort();
    expect(zhKeys).toEqual(enKeys);
  });
});

describe("loadMessages", () => {
  it("returns the cached default messages for zh-CN without dynamic import", async () => {
    const msgs = await loadMessages("zh-CN");
    expect(msgs).toBe(defaultMessages);
  });

  it("loads en-US messages and populates the synchronous cache", async () => {
    const msgs = await loadMessages("en-US");
    expect(msgs.overview).toBe("Overview");
    // 同步 t 函数在加载完成后应能读取 en-US
    expect(t("en-US", "overview")).toBe("Overview");
    // 再次加载应返回同一引用（缓存）
    const cached = await loadMessages("en-US");
    expect(cached).toBe(msgs);
  });

  it("falls back to default messages before en-US is loaded", () => {
    // 重置 en-US 缓存为 fallback，验证加载前的回退行为
    setMessagesForLocale("en-US", defaultMessages as Messages);
    expect(t("en-US", "overview")).toBe("概览");
  });
});
