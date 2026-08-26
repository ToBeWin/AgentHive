import { defaultLocale, defaultMessages, loadLocaleMessages } from "./i18n/messages";
import type { Locale, Messages } from "./i18n/messages/types";

export type { Locale, Messages };
export { defaultLocale };

export const LOCALE_STORAGE_KEY = "agenthive.locale";

// 模块级缓存：默认语言同步填充，其他语言由 loadMessages 注入
const loadedMessages: Record<Locale, Messages> = {
  "en-US": defaultMessages,
  "zh-CN": defaultMessages,
};

const loadedLocales = new Set<Locale>([defaultLocale]);
const loadingPromises = new Map<Locale, Promise<Messages>>();

// 保留同步访问 API：messages 反映当前已加载的语言包
export const messages: Record<Locale, Messages> = loadedMessages;

const LOCALES = new Set<Locale>(["en-US", "zh-CN"]);

export function t(locale: Locale, key: string): string {
  const msgs = loadedMessages[locale] ?? loadedMessages[defaultLocale];
  return msgs[key] ?? key;
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && LOCALES.has(value as Locale);
}

export function getStoredLocale(): Locale {
  if (typeof window === "undefined") {
    return defaultLocale;
  }

  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (isLocale(stored)) {
      return stored;
    }
  } catch {
    return defaultLocale;
  }

  return defaultLocale;
}

export function saveLocale(locale: Locale) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Browser privacy settings can block localStorage. The in-memory locale still works.
  }
}

// 供测试或外部调用注入已加载消息
export function setMessagesForLocale(locale: Locale, msgs: Messages) {
  loadedMessages[locale] = msgs;
  loadedLocales.add(locale);
}

// 异步加载语言包：已加载则直接返回缓存，否则动态 import 并注入
export function loadMessages(locale: Locale): Promise<Messages> {
  if (loadedLocales.has(locale)) {
    return Promise.resolve(loadedMessages[locale]);
  }
  const existing = loadingPromises.get(locale);
  if (existing) {
    return existing;
  }
  const promise = loadLocaleMessages(locale).then((msgs) => {
    setMessagesForLocale(locale, msgs);
    loadingPromises.delete(locale);
    return msgs;
  });
  loadingPromises.set(locale, promise);
  return promise;
}
