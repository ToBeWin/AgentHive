export function apiProxyTarget(env: Record<string, string | undefined>): string {
  return env.VITE_API_PROXY_TARGET?.trim() || "http://localhost:8000";
}
