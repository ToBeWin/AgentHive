---
name: AgentHive Design System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3d4947'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#6d7a77'
  outline-variant: '#bcc9c6'
  surface-tint: '#006a61'
  primary: '#00685f'
  on-primary: '#ffffff'
  primary-container: '#008378'
  on-primary-container: '#f4fffc'
  inverse-primary: '#6bd8cb'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#595c5e'
  on-tertiary: '#ffffff'
  tertiary-container: '#727577'
  on-tertiary-container: '#fbfdff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#89f5e7'
  primary-fixed-dim: '#6bd8cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#005049'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#e0e3e5'
  tertiary-fixed-dim: '#c4c7c9'
  on-tertiary-fixed: '#191c1e'
  on-tertiary-fixed-variant: '#444749'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  container-max: 1440px
  gutter: 16px
---

## Brand & Style

The design system is engineered for private-deployment enterprise AI environments where clarity, reliability, and data density are paramount. The brand personality is **Technical, Authoritative, and Transparent**, moving away from "magical" AI tropes toward a functional, tool-oriented aesthetic.

The visual style is **Corporate Modern with a Minimalist execution**. It prioritizes high information density and structural logic over decorative elements. The UI evokes a sense of calm control through significant white space within functional clusters, ensuring that complex agentic workflows remain legible and professional. This is a "workhorse" interface designed for long-duration cognitive tasks.

## Colors

The palette is anchored by a neutral foundation to reduce cognitive load, punctuated by a confident teal for action and intent.

- **Primary (Teal #0D9488):** Represents active agents, successful operations, and primary calls to action. It is professional and high-contrast against light backgrounds.
- **Secondary (Slate #0F172A):** Used for primary text and structural sidebars, providing a grounded, professional feel.
- **Neutral (Slate Gray #64748B):** Applied to borders, secondary icons, and metadata.
- **Backgrounds:** A tiered system of White (#FFFFFF) for cards/content and a soft Off-White (#F8FAFC) for the application canvas to create subtle depth without shadows.

**Status Mapping:**
- **Success:** Teal-600
- **Warning:** Amber-500 (Used sparingly for agent bottlenecks)
- **Error:** Rose-600 (Used for deployment failures)
- **Neutral/Idle:** Slate-400

## Typography

The design system utilizes **Geist** for its exceptional legibility in data-heavy environments and its technical, "developer-friendly" feel. 

**Localization Strategy:** 
For Simplified Chinese support, the system falls back to **Noto Sans SC**. Line heights are maintained at 1.5x for body text to ensure Chinese characters remain legible and do not feel cramped. Weight transitions are kept minimal (Regular 400 and Semibold 600) to maintain a clean hierarchy. Monospaced text (JetBrains Mono) is used exclusively for agent logs and API configurations.

## Layout & Spacing

This design system uses a **Fixed-Fluid Hybrid Grid**. Sidebars and right-side drawers have fixed widths, while the primary content area is fluid with a maximum container width of 1440px to prevent excessive line lengths on ultra-wide monitors.

**High-Density Principles:**
- Use a 4px baseline grid.
- Tables and lists use a "compact" vertical rhythm (8px padding).
- Content is grouped in clearly defined regions using 1px borders rather than wide margins.

**Breakpoints:**
- **Mobile (<768px):** Single column, navigation moves to a bottom bar or hamburger menu.
- **Tablet (768px - 1024px):** Collapsed sidebar, fluid content.
- **Desktop (>1024px):** Fixed 240px sidebar, fluid content, 400px fixed-width right drawers for agent configuration.

## Elevation & Depth

To maintain a "flat" enterprise aesthetic, depth is conveyed through **Tonal Layering and Low-Contrast Outlines** rather than heavy shadows.

1.  **Level 0 (Canvas):** #F8FAFC. The foundation layer.
2.  **Level 1 (Cards/Sidebar):** #FFFFFF. Used for the primary workspace and navigation. 1px border in #E2E8F0.
3.  **Level 2 (Drawers/Modals):** #FFFFFF. These use a subtle, extra-diffused shadow (0px 10px 15px -3px rgba(0,0,0,0.05)) to suggest they are floating above the main workspace.
4.  **Interaction:** Hover states on interactive elements use a subtle gray background shift (#F1F5F9) rather than an elevation increase.

## Shapes

The shape language is **Structured and Precise**. A consistent **4px to 8px radius** is applied to emphasize a technical, tool-like feel. 

- **Small elements (Buttons, Inputs, Checkboxes):** 4px radius.
- **Medium elements (Cards, Drawers, Modals):** 8px radius.
- **Status Badges:** Fully rounded (pill) to distinguish them from interactive buttons.

This geometric approach reinforces the enterprise-ready nature of the platform.

## Components

### Buttons
- **Primary:** Solid Teal (#0D9488) with White text. 4px radius.
- **Secondary:** White background with #E2E8F0 border.
- **Ghost:** No border/background until hover. Used for table actions.

### Data Tables
Tables are the heart of the platform. They must support:
- **Condensed Row Height:** 40px for high-density viewing.
- **Sticky Headers:** Always visible during scroll.
- **Inline Status:** Circular indicators with label-md typography.

### Right-Side Drawers
Used for "Agent Configuration" or "Log Details." 
- **Width:** 400px - 480px.
- **Entry:** Slides in from the right, pushing or overlaying content with a light backdrop blur.
- **Footer:** Fixed action bar for "Save" or "Deploy."

### Form Fields
- **Inputs:** 1px border (#E2E8F0), 4px radius, Geist 14px text. 
- **Focus State:** 1px Teal border with a 2px soft teal outer glow (ring).

### Icons
- **Style:** Lucide-style line icons. 1.5px stroke width.
- **Size:** 16px for inline text, 20px for primary navigation.

### Status Badges
- Small, uppercase labels with a 10% opacity background of their status color and 100% opacity text.
- Example: `ACTIVE` has #0D9488 text on a 10% teal background.