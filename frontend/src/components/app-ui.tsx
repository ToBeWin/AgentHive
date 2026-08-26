import { AlertTriangle, CheckCircle, Info, Loader2, X, XCircle } from "lucide-react";
import {
  type CSSProperties,
  createContext,
  type MouseEventHandler,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type Ref,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useEscapeKey } from "../hooks/useEscapeKey";
import { useLocale } from "../i18n-context";

export function cx(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(" ");
}

type ToastVariant = "success" | "error" | "info" | "warning";

interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: string;
}

const ToastContext = createContext<{ showToast: (message: string, variant?: ToastVariant) => void } | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const { t } = useLocale();

  const showToast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, variant, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <section className="toast-container" aria-label={t("commonNotificationsRegion")}>
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cx("toast", `toast-${toast.variant}`)}
            role="status"
            aria-live={toast.variant === "error" ? "assertive" : "polite"}
          >
            {toast.variant === "success" && <CheckCircle size={16} aria-hidden="true" />}
            {toast.variant === "error" && <XCircle size={16} aria-hidden="true" />}
            {toast.variant === "warning" && <AlertTriangle size={16} aria-hidden="true" />}
            {toast.variant === "info" && <Info size={16} aria-hidden="true" />}
            <span>{toast.message}</span>
            <button onClick={() => removeToast(toast.id)} type="button" aria-label={t("commonClose")}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        ))}
      </section>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return { showToast: () => {} };
  }
  return ctx;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  variant = "danger",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useLocale();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<Element | null>(null);
  const titleId = "confirm-dialog-title";
  const descId = "confirm-dialog-desc";
  const resolvedCancelLabel = cancelLabel || t("commonClose");
  const resolvedConfirmLabel = confirmLabel || t("commonRetry");

  // Focus management: when the dialog opens, capture the current focus and
  // move it onto the confirm button so keyboard users land inside the modal.
  // When it closes, restore focus to the element that opened it.
  useEffect(() => {
    if (!open) {
      return;
    }
    previouslyFocusedRef.current = document.activeElement;
    // Defer one tick so the buttons are mounted before we focus them.
    const timer = window.setTimeout(() => {
      confirmButtonRef.current?.focus();
    }, 0);
    return () => {
      window.clearTimeout(timer);
      const previous = previouslyFocusedRef.current;
      if (previous instanceof HTMLElement) {
        previous.focus();
      }
    };
  }, [open]);

  // Focus trap + Esc handling: keep Tab focus inside the dialog and close
  // on Escape. Esc is also handled by the overlay keydown fallback below.
  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCancel();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const root = dialogRef.current;
      if (!root) {
        return;
      }
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'),
      ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !root.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div className="confirm-overlay">
      <button type="button" className="confirm-backdrop" aria-label={resolvedCancelLabel} onClick={onCancel} />
      <div
        ref={dialogRef}
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            onCancel();
          }
        }}
      >
        <h3 id={titleId}>{title}</h3>
        <p id={descId}>{message}</p>
        <div className="confirm-actions">
          <Button variant="ghost" onClick={onCancel}>
            {resolvedCancelLabel}
          </Button>
          <Button ref={confirmButtonRef} variant={variant === "danger" ? "danger" : "primary"} onClick={onConfirm}>
            {resolvedConfirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function StatusBadge({ label, status }: { label?: string; status: string }) {
  const key = status.toLowerCase().replace(/\s/g, "-");
  return <span className={cx("status", `status-${key}`)}>{label ?? status}</span>;
}

export function ApiNotice({
  title,
  message,
  action,
  errorDetail,
  onRetry,
}: {
  title: string;
  message: string;
  action?: ReactNode;
  errorDetail?: string;
  onRetry?: () => void;
}) {
  const { t } = useLocale();
  const [showDetail, setShowDetail] = useState(false);
  return (
    <div className="api-notice" role="alert">
      <div className="api-notice-icon" aria-hidden="true">
        <AlertTriangle size={20} />
      </div>
      <div className="api-notice-body">
        <strong className="api-notice-title">{title}</strong>
        <p className="api-notice-message">{message}</p>
        <div className="api-notice-actions">
          {onRetry && (
            <Button variant="secondary" onClick={onRetry}>
              {t("commonRetry")}
            </Button>
          )}
          {action}
          {errorDetail && (
            <button
              type="button"
              className="api-notice-detail-toggle"
              onClick={() => setShowDetail((v) => !v)}
              aria-expanded={showDetail}
            >
              {showDetail ? t("commonHideDetails") : t("commonShowDetails")}
            </button>
          )}
        </div>
        {showDetail && errorDetail && <pre className="api-notice-detail">{errorDetail}</pre>}
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function PageTabs<T extends string>({
  active,
  onChange,
  tabs,
}: {
  active: T;
  onChange: (id: T) => void;
  tabs: Array<{ id: T; label: string; description?: string }>;
}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const activeIndex = Math.max(
    0,
    tabs.findIndex((tab) => tab.id === active),
  );
  const selectTab = (index: number) => {
    const nextIndex = (index + tabs.length) % tabs.length;
    onChange(tabs[nextIndex].id);
    tabRefs.current[nextIndex]?.focus();
  };
  const handleKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!tabs.length) {
      return;
    }
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      selectTab(index + 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      selectTab(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectTab(tabs.length - 1);
    }
  };

  return (
    <div className="page-tabs" role="tablist" aria-orientation="horizontal">
      {tabs.map((tab, index) => (
        <button
          type="button"
          key={tab.id}
          ref={(node) => {
            tabRefs.current[index] = node;
          }}
          className={cx("page-tab", active === tab.id && "active")}
          onClick={() => onChange(tab.id)}
          onKeyDown={(event) => handleKeyDown(event, index)}
          role="tab"
          aria-selected={active === tab.id}
          tabIndex={index === activeIndex ? 0 : -1}
          title={tab.description}
        >
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Button({
  children,
  variant = "secondary",
  onClick,
  disabled,
  type = "button",
  loading = false,
  ref,
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  onClick?: MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  loading?: boolean;
  ref?: Ref<HTMLButtonElement>;
}) {
  const [showSpinner, setShowSpinner] = useState(false);
  useEffect(() => {
    if (!loading) {
      setShowSpinner(false);
      return;
    }
    const timer = window.setTimeout(() => setShowSpinner(true), 500);
    return () => window.clearTimeout(timer);
  }, [loading]);
  return (
    <button ref={ref} type={type} className={cx("button", variant)} onClick={onClick} disabled={disabled || loading}>
      {showSpinner && <Loader2 size={14} className="button-spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function FieldLabel({
  children,
  required = false,
  htmlFor,
}: {
  children: ReactNode;
  required?: boolean;
  htmlFor?: string;
}) {
  const { t } = useLocale();
  return (
    <label
      htmlFor={htmlFor}
      className={cx("field-label", required && "required")}
      title={required ? t("commonRequired") : undefined}
    >
      {children}
      {required && (
        <span className="field-required-mark" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}

export function CharCounter({ value, max, threshold = 0.9 }: { value: number; max: number; threshold?: number }) {
  const ratio = max > 0 ? value / max : 0;
  const variant = ratio >= 1 ? "over" : ratio >= threshold ? "warn" : "ok";
  return (
    <span className={cx("char-counter", `char-counter-${variant}`)} aria-live="polite">
      {value} / {max}
    </span>
  );
}

export function Skeleton({
  width,
  height,
  rounded,
  lines,
}: {
  width?: string | number;
  height?: string | number;
  rounded?: boolean;
  lines?: number;
}) {
  if (lines && lines > 1) {
    const lineItems = Array.from({ length: lines }, (_, index) => ({
      id: `skeleton-line-${index}`,
      isLast: index === lines - 1,
    }));
    return (
      <div className="skeleton-lines" aria-hidden>
        {lineItems.map((item) => (
          <span key={item.id} className={cx("skeleton-line", item.isLast && "skeleton-line-short")} />
        ))}
      </div>
    );
  }
  const style: CSSProperties = {};
  if (width !== undefined) {
    style.width = typeof width === "number" ? `${width}px` : width;
  }
  if (height !== undefined) {
    style.height = typeof height === "number" ? `${height}px` : height;
  }
  return <span className={cx("skeleton", rounded && "skeleton-rounded")} style={style} aria-hidden />;
}

export function LoadingState({ message, lines = 3 }: { message?: string; lines?: number }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <Skeleton lines={lines} />
      {message && <p className="loading-state-message">{message}</p>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  message,
  action,
}: {
  icon?: ReactNode;
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state" role="status">
      {icon && (
        <div className="empty-state-icon-wrapper">
          <span className="empty-state-icon-ring" aria-hidden="true" />
          <span className="empty-state-icon">{icon}</span>
        </div>
      )}
      <h3 className="empty-state-title">{title}</h3>
      {message && <p className="empty-state-message">{message}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}

/**
 * Panel — unified section container with optional title, subtitle and actions.
 * Replaces the repeated `<section className="panel"><div className="panel-title">` pattern.
 */
export function Panel({
  title,
  subtitle,
  actions,
  className,
  children,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx("panel", className)}>
      {(title || actions) && (
        <div className="panel-title">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <span className="panel-subtitle">{subtitle}</span>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * Drawer — slide-in panel with backdrop, Esc-to-close, header and footer.
 * Replaces the repeated backdrop + aside + header + content + footer pattern.
 */
export function Drawer({
  open,
  title,
  subtitle,
  onClose,
  footer,
  className,
  ariaLabel,
  children,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  footer?: ReactNode;
  className?: string;
  ariaLabel?: string;
  children: ReactNode;
}) {
  const { t } = useLocale();
  const drawerRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<Element | null>(null);
  useEscapeKey(onClose, open);

  useEffect(() => {
    if (!open) {
      return;
    }
    previouslyFocusedRef.current = document.activeElement;
    const timer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") {
        return;
      }
      const root = drawerRef.current;
      if (!root) {
        return;
      }
      const focusable = Array.from(
        root.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'),
      ).filter((element) => !element.hasAttribute("disabled"));
      if (focusable.length === 0) {
        event.preventDefault();
        root.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("keydown", handleKeyDown, true);
      const previous = previouslyFocusedRef.current;
      if (previous instanceof HTMLElement) {
        previous.focus();
      }
    };
  }, [open]);

  if (!open) return null;
  return (
    <>
      <button type="button" aria-label={t("commonClose")} className="drawer-backdrop" onClick={onClose} />
      <aside
        ref={drawerRef}
        className={cx("drawer", className)}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel ?? title}
        tabIndex={-1}
      >
        <header>
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <Button ref={closeButtonRef} variant="ghost" onClick={onClose}>
            <X size={16} /> {t("commonClose")}
          </Button>
        </header>
        <div className="drawer-content">{children}</div>
        {footer && <footer>{footer}</footer>}
      </aside>
    </>
  );
}

/**
 * FormField — label + input wrapper with error/hint display.
 * Replaces the repeated `<label>{text}<input/>{error}</label>` pattern.
 */
export function FormField({
  label,
  htmlFor,
  error,
  hint,
  required,
  className,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string | null;
  hint?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cx("form-field", error ? "form-field-has-error" : undefined, className)}>
      <FieldLabel htmlFor={htmlFor} required={required}>
        {label}
      </FieldLabel>
      {children}
      {error ? (
        <span className="form-field-error">{error}</span>
      ) : hint ? (
        <span className="form-field-hint">{hint}</span>
      ) : null}
    </div>
  );
}
