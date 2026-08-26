import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { getStoredLocale, t as translateMessage } from "../i18n";
import { ApiNotice, Button } from "./app-ui";

type BoundaryState = {
  error: Error | null;
};

type BoundaryProps = {
  children: ReactNode;
  fallbackTitle: string;
  fallbackMessage: string;
  onReset: () => void;
  resetLabel: string;
  resetKey: string;
};

class PageErrorBoundaryInner extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("AgentHive page render failed", { error, errorInfo });
  }

  componentDidUpdate(previousProps: BoundaryProps) {
    if (previousProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <section className="page">
        <ApiNotice
          title={this.props.fallbackTitle}
          message={`${this.props.fallbackMessage} ${this.state.error.message}`}
          action={<Button onClick={this.props.onReset}>{this.props.resetLabel}</Button>}
        />
      </section>
    );
  }
}

export function PageErrorBoundary({
  children,
  fallbackMessage,
  fallbackTitle,
  resetKey,
  resetLabel,
}: {
  children: ReactNode;
  fallbackMessage: string;
  fallbackTitle: string;
  resetKey: string;
  resetLabel: string;
}) {
  return (
    <PageErrorBoundaryInner
      fallbackMessage={fallbackMessage}
      fallbackTitle={fallbackTitle}
      resetKey={resetKey}
      resetLabel={resetLabel}
      onReset={() => window.location.reload()}
    >
      {children}
    </PageErrorBoundaryInner>
  );
}

type RootBoundaryState = {
  error: Error | null;
};

/**
 * Top-level error boundary sitting outside LocaleProvider/ToastProvider so it
 * can recover from rendering failures that escape the AppShell. Uses the
 * synchronous translation entry point (with the persisted locale) so the
 * fallback UI works without React context.
 */
export class RootErrorBoundary extends Component<{ children: ReactNode }, RootBoundaryState> {
  state: RootBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[RootErrorBoundary]", error, info);
  }

  handleDismiss = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }
    const locale = getStoredLocale();
    const title = translateMessage(locale, "commonErrorBoundaryTitle");
    const message = translateMessage(locale, "commonErrorBoundaryMessage");
    const reloadLabel = translateMessage(locale, "commonReload");
    const dismissLabel = translateMessage(locale, "commonDismiss");
    return (
      <div className="root-error" role="alert">
        <div className="root-error-card">
          <AlertTriangle size={40} aria-hidden="true" />
          <h1>{title}</h1>
          <p>{message}</p>
          <div className="root-error-actions">
            <Button variant="primary" onClick={() => window.location.reload()}>
              {reloadLabel}
            </Button>
            <Button variant="ghost" onClick={this.handleDismiss}>
              {dismissLabel}
            </Button>
          </div>
          {import.meta.env.DEV && error.stack && <pre className="root-error-stack">{error.stack}</pre>}
        </div>
      </div>
    );
  }
}
