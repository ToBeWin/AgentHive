import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { defaultLocale, type Locale, loadMessages, t as translateMessage } from "./i18n";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({
  children,
  locale,
  setLocale,
}: {
  children: ReactNode;
  locale: Locale;
  setLocale: (locale: Locale) => void;
}) {
  // 使用已加载的 locale，避免未加载时显示 key
  const [loadedLocale, setLoadedLocale] = useState<Locale>(defaultLocale);

  useEffect(() => {
    let cancelled = false;
    void loadMessages(locale).then(() => {
      if (!cancelled) {
        setLoadedLocale(locale);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const value = useMemo(
    () => ({
      locale: loadedLocale,
      setLocale,
      t: (key: string) => translateMessage(loadedLocale, key),
    }),
    [loadedLocale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const value = useContext(LocaleContext);
  if (!value) {
    throw new Error("useLocale must be used within LocaleProvider.");
  }
  return value;
}
