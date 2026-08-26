import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { RootErrorBoundary } from "./components/PageErrorBoundary";
import "highlight.js/styles/github-dark-dimmed.css";
import "./styles/base.css";
import "./styles/layout.css";
import "./styles/components.css";
import "./styles/chat.css";
import "./styles/agents.css";
import "./styles/knowledge.css";
import "./styles/models.css";
import "./styles/media.css";
import "./styles/settings.css";
import "./styles/employee.css";
import "./styles/channels.css";
import "./styles/admin.css";
import "./styles/builder.css";
import "./styles/auth.css";
import "./styles/animations.css";
import "./styles/utilities.css";
import "./styles/responsive.css";
import "./styles/responsive-refinements.css";

// Optional Sentry initialisation. Vite inlines VITE_SENTRY_DSN at build time;
// when unset (the default), this is a no-op and @sentry/react is never loaded.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
if (sentryDsn) {
  import("@sentry/react")
    .then((Sentry) => {
      Sentry.init({
        dsn: sentryDsn,
        environment: import.meta.env.MODE,
        tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0) || 0,
      });
    })
    .catch(() => {
      // @sentry/react not installed; skip silently.
    });
}

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element #root not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </StrictMode>,
);
