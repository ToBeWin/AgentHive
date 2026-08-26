import { Bot, Database, MessageSquare } from "lucide-react";
import type { ReactNode } from "react";
import type { Locale } from "../../i18n";
import { useLocale } from "../../i18n-context";

function HexPattern() {
  return (
    <svg
      className="hex-pattern"
      viewBox="0 0 400 300"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="hexGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="rgba(255,255,255,0.4)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0.1)" />
        </linearGradient>
      </defs>
      <line x1="200" y1="150" x2="100" y2="80" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
      <line x1="200" y1="150" x2="300" y2="80" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
      <line x1="200" y1="150" x2="100" y2="220" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
      <line x1="200" y1="150" x2="300" y2="220" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
      <polygon
        points="200,110 235,130 235,170 200,190 165,170 165,130"
        fill="url(#hexGrad)"
        stroke="rgba(255,255,255,0.6)"
        strokeWidth="1.5"
      />
      <polygon
        points="100,50 120,62 120,86 100,98 80,86 80,62"
        fill="rgba(255,255,255,0.15)"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="1"
      />
      <polygon
        points="300,50 320,62 320,86 300,98 280,86 280,62"
        fill="rgba(255,255,255,0.15)"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="1"
      />
      <polygon
        points="100,200 120,212 120,236 100,248 80,236 80,212"
        fill="rgba(255,255,255,0.15)"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="1"
      />
      <polygon
        points="300,200 320,212 320,236 300,248 280,236 280,212"
        fill="rgba(255,255,255,0.15)"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="1"
      />
    </svg>
  );
}

export function AuthShell({ children }: { children: ReactNode }) {
  const { locale, setLocale, t } = useLocale();

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-brand">
          <div className="brand-mark">✣</div>
          <div>
            <strong>AgentHive</strong>
            <span>{t("commonProductTagline")}</span>
          </div>
        </div>
        <label className="auth-language">
          <span>{t("language")}</span>
          <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
            <option value="zh-CN">{t("authLanguageChinese")}</option>
            <option value="en-US">{t("authLanguageEnglish")}</option>
          </select>
        </label>
        {children}
      </section>
      <aside className="auth-aside">
        <div className="auth-brand-hero">
          <div className="auth-brand-logo">
            <span className="auth-brand-mark" aria-hidden="true">
              ✣
            </span>
            <span className="auth-brand-name">AgentHive</span>
          </div>
          <h2 className="auth-brand-slogan">{t("authBrandSlogan")}</h2>
          <p className="auth-brand-subtitle">{t("authBrandSubtitle")}</p>

          <div className="auth-brand-visual" aria-hidden="true">
            <HexPattern />
          </div>

          <ul className="auth-brand-highlights">
            <li>
              <Bot size={20} aria-hidden="true" />
              <div>
                <strong>{t("authHighlightAgentsTitle")}</strong>
                <span>{t("authHighlightAgentsDesc")}</span>
              </div>
            </li>
            <li>
              <MessageSquare size={20} aria-hidden="true" />
              <div>
                <strong>{t("authHighlightChannelsTitle")}</strong>
                <span>{t("authHighlightChannelsDesc")}</span>
              </div>
            </li>
            <li>
              <Database size={20} aria-hidden="true" />
              <div>
                <strong>{t("authHighlightKnowledgeTitle")}</strong>
                <span>{t("authHighlightKnowledgeDesc")}</span>
              </div>
            </li>
          </ul>
        </div>
      </aside>
    </main>
  );
}
