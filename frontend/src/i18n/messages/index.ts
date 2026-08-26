// 默认语言同步导入，避免首屏闪烁

import type { Locale, Messages } from "./types";
import { zhCNMessages } from "./zh-CN";

export const defaultMessages: Messages = zhCNMessages;
export const defaultLocale: Locale = "zh-CN";

// 其他语言通过动态 import 拆分 chunk
export async function loadLocaleMessages(locale: Locale): Promise<Messages> {
  switch (locale) {
    case "zh-CN":
      return zhCNMessages;
    case "en-US": {
      const mod = await import("./en-US");
      return mod.enUSMessages;
    }
  }
}
