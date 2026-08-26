# AgentHive UI Design System Contract

This document keeps the product UI aligned with the local AgentHive visual reference and the shipped frontend tokens. It is an implementation contract for the management console, not a marketing style guide.

## Source Of Truth

- Visual reference: `stitch_agenthive_enterprise_ui_design/agenthive_design_system/DESIGN.md`
- Editable Pen reference: `agenthive-ui.pen`
- Runtime tokens: `frontend/src/styles/base.css`
- Responsive behavior: `frontend/src/styles/responsive-refinements.css`
- Shared primitives: `frontend/src/components/app-ui.tsx`

When a page needs a new value, prefer an existing token or shared primitive. A page-local hex color, radius, shadow, or breakpoint needs a concrete product reason and a focused test or screenshot check.

## Product Expression

AgentHive should feel like a calm operations console for an enterprise AI system:

- Make ownership, status, cost, and next action legible before configuration detail.
- Use restrained surfaces and strong typography hierarchy instead of decorative cards or gradients.
- Keep management workflows dense enough for repeated work, while preserving generous focus states and readable empty/error states.
- Treat private deployment, governance, auditability, and role-aware access as visible product qualities, not hidden implementation details.

## Tokens

| Role | Token | Value |
| --- | --- | --- |
| Page background | `--bg` | `#f6f8fb` |
| Surface | `--surface` | `#ffffff` |
| Soft surface | `--surface-soft` | `#f3f7fb` |
| Primary text | `--text` | `#0b1c30` |
| Secondary text | `--muted` | `#4b5b68` |
| Faint text | `--faint` | `#7b8994` |
| Divider | `--line` | `#cbd5dd` |
| Soft divider | `--line-soft` | `#e1e8ed` |
| Primary action | `--primary` | `#006a61` |
| Secondary primary | `--primary-2` | `#0d9488` |
| Primary tint | `--primary-soft` | `#dff3ef` |
| Success | `--success-soft` | `#dff3ef` |
| Warning | `--warning` | `#b45309` |
| Danger | `--danger` | `#ba1a1a` |

Use `Geist` first and `Noto Sans SC` for Chinese fallback. The spacing scale is 4px based: `4 / 8 / 12 / 16 / 20 / 24`. Use `4 / 6 / 8px` corners for functional surfaces and reserve full rounding for status pills or avatars.

## Layout Rules

- Desktop navigation is a stable 240px rail. The content area owns its own 24px or 40px inner rhythm.
- A page section is an unframed layout band. Use cards only for repeated records, framed tools, modals, and explicit KPI surfaces.
- Do not nest a card inside another card just to create hierarchy. Use spacing, headings, dividers, and surface contrast first.
- KPI values must not wrap currency or identifiers into unreadable fragments. Use `.metric-value` and allow the value to move to a new line when the viewport is narrow.
- Tables and dense grids need a deliberate mobile mode: stacked rows, horizontal scrolling with an explicit container, or a compact list. Never rely on accidental viewport overflow.
- Keep headings short and action-oriented. A page title owns the screen; compact panels use section-scale headings, not hero-scale typography.

## Responsive Contract

| Viewport | Expected behavior |
| --- | --- |
| `1440x900` | Full navigation rail, balanced KPI row, two-column analysis panels, quick actions in one row. |
| `768x900` | Collapsed navigation, two-column actionable grids where content still fits, no clipped notices or buttons. |
| `390x844` | Drawer navigation, one-column actions and KPIs, wrapped notices, no horizontal page overflow, primary action remains reachable. |

The mobile drawer must have an accessible name, an explicit backdrop, Escape handling, and focus-visible controls. A layout change is incomplete until these three viewport classes are checked for `scrollWidth === clientWidth` on the page shell and the main user workflow.

## State And Interaction Language

- `success`: the system can proceed and the user does not need to intervene.
- `warning`: the workflow is usable but needs attention or has a known optional limitation.
- `danger`: the workflow is blocked or a destructive action needs confirmation.
- `neutral`: the system is waiting, empty, or not yet configured.

User-facing API notices must use localized, human-readable messages. Raw transport details, URLs, stack traces, and provider secrets stay in diagnostics or audit views. Retryable failures expose a retry action; empty states explain the next useful action without pretending data exists.

Buttons and icon controls keep native semantics, visible focus, and an accessible name. Prefer existing Lucide icons and shared `Button`, `StatusBadge`, `ApiNotice`, and form primitives over page-local imitations.

## Review Checklist

Before accepting a UI change, verify:

- the page uses the token palette and does not introduce an unrelated visual theme;
- the main task, status, ownership, and next action are clear above the fold;
- loading, empty, error, retry, and success states are all readable;
- keyboard focus and screen-reader names remain intact;
- 390px, 768px, and 1440px screenshots show no incoherent overlap or overflow;
- the change has the smallest useful component or visual regression test;
- the corresponding backend error and permission states remain localized and role-aware.

The current desktop Pen session is owned by another project and must remain untouched. AgentHive now has a dedicated `agenthive-ui.pen` reference file containing the overview desktop/mobile composition and the same token vocabulary; future screen refinements should extend that file and this checklist rather than silently creating a second visual language.
