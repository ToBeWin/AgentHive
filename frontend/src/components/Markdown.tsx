import { Check, Copy } from "lucide-react";
import { memo, type ReactNode, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { useLocale } from "../i18n-context";

interface MarkdownProps {
  children: string;
  className?: string;
}

/**
 * Render assistant message content as GitHub-flavoured Markdown with syntax
 * highlighting. Each code block is wrapped in a `.code-block-wrapper` that
 * exposes a hover-to-reveal copy button.
 */
export const Markdown = memo(function Markdown({ children, className }: MarkdownProps) {
  if (!children) {
    return null;
  }
  return (
    <div className={cx("message-content markdown-body", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{ pre: ({ children: preChildren }) => <CodeBlock>{preChildren}</CodeBlock> }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
});

function CodeBlock({ children }: { children?: ReactNode }) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const text = extractText(children);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable; ignore
    }
  };

  return (
    <div className="code-block-wrapper">
      <button type="button" className="code-block-copy" onClick={handleCopy} aria-label={t("chatCopyCode")}>
        {copied ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
        {copied ? t("chatCodeCopied") : t("chatCopyCode")}
      </button>
      <pre>{children}</pre>
    </div>
  );
}

// Recursively extract plain text from react-markdown's rendered code element
// (which may contain syntax-highlight spans from rehype-highlight).
function extractText(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

function cx(...parts: Array<string | undefined | false>): string {
  return parts.filter(Boolean).join(" ");
}
