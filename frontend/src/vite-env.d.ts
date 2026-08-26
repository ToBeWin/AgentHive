/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_SENTRY_TRACES_SAMPLE_RATE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Node globals used by vite.config.ts and playwright.config.ts at build time.
declare const process: {
  readonly env: Record<string, string | undefined>;
  readonly CI?: string;
};
