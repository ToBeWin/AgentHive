const SETUP_DATABASE_UNAVAILABLE = "AgentHive database is unavailable. Check PostgreSQL before continuing setup.";

export function localizedAuthError(caught: unknown, fallback: string, t: (key: string) => string) {
  const message = caught instanceof Error ? caught.message : typeof caught === "string" ? caught : fallback;
  if (message === SETUP_DATABASE_UNAVAILABLE) {
    return t("authDatabaseUnavailable");
  }
  return message || fallback;
}
