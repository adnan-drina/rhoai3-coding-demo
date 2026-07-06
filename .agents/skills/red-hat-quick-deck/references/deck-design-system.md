# Deck Design System

## Design System

### Red Hat Design Tokens

This skill integrates the official **Red Hat Design Tokens** (`@rhds/tokens`) for spacing, typography sizing,
borders, and shadows. The tokens CSS is loaded via jsDelivr CDN alongside the existing Google Fonts and
`@rhds/icons` dependencies. All token references include hardcoded fallbacks so decks degrade gracefully offline.

**CDN URL:**
```
https://cdn.jsdelivr.net/npm/@rhds/tokens@3.0.2/css/global.min.css
```

**Important color note:** The RHDS v3 tokens use accessibility-adjusted color values (e.g.,
`--rh-color-brand-red-on-dark` resolves to `#FF442B`, not `#ee0000`). This skill intentionally keeps
the established Red Hat brand palette hex values (`#ee0000` for red-50, etc.) for visual consistency
with the classic brand aesthetic. Token names are annotated in comments for cross-reference.

**What we use from `@rhds/tokens`:**
- **Spacing**: `--rh-space-xs` (4px) through `--rh-space-7xl` (128px) — consistent 4px-base scale
- **Typography sizing**: `--rh-font-size-heading-*` and `--rh-font-size-body-text-*`
- **Font families**: `--rh-font-family-heading`, `--rh-font-family-body-text`, `--rh-font-family-code`
- **Border radius**: `--rh-border-radius-default` (3px), `--rh-border-radius-pill` (64px)
- **Border width**: `--rh-border-width-sm` (1px), `--rh-border-width-md` (2px), `--rh-border-width-lg` (3px)
- **Box shadows**: `--rh-box-shadow-sm/md/lg/xl` — for cards, architecture boxes, elevated surfaces
- **Opacity**: `--rh-opacity-*` — for overlays, muted elements, and glow effects

**Token reference:** https://ux.redhat.com/tokens/ · Package: https://www.npmjs.com/package/@rhds/tokens

### Color Palette Selection

Choose ONE color collection per deck from the Red Hat brand palette. The **default and recommended**
collection is **"Core Dark"** which matches the reference screenshot aesthetic.

Each mode sets `color-scheme` on `:root` so that any `light-dark()` token values resolve correctly.

**Core Dark (Default)**
```css
:root { color-scheme: dark; }

--bg-primary: #000000;        /* black · --rh-color-surface-darkest */
--bg-secondary: #1f1f1f;      /* gray-90 · --rh-color-surface-darker */
--bg-surface: #292929;         /* gray-80 · --rh-color-surface-dark */
--text-primary: #ffffff;       /* white · --rh-color-text-primary-on-dark */
--text-secondary: #c7c7c7;    /* gray-30 · --rh-color-text-secondary-on-dark */
--text-muted: #a3a3a3;         /* gray-40 */
--accent: #ee0000;             /* red-50 — Red Hat Red */
--accent-dark: #a60000;        /* red-60 */
--accent-light: #f56e6e;       /* red-40 */
--tag-border: #383838;         /* gray-70 · --rh-color-border-subtle-on-dark */
--icon-filter: brightness(0) invert(1);  /* white icons on dark bg */
--icon-filter-accent: invert(12%) sepia(100%) saturate(10000%) hue-rotate(0deg) brightness(95%); /* red-50 icons */
```

Other available collections (use when the user requests a different feel):

**Core Light** (clean, professional — best for print/email/documentation)
```css
:root { color-scheme: light; }

--bg-primary: #ffffff;         /* white · --rh-color-surface-lightest */
--bg-secondary: #f2f2f2;      /* gray-10 · --rh-color-surface-lighter */
--bg-surface: #e0e0e0;        /* gray-20 · --rh-color-surface-light */
--text-primary: #151515;      /* gray-95 · --rh-color-text-primary-on-light */
--text-secondary: #4d4d4d;    /* gray-60 · --rh-color-text-secondary-on-light */
--text-muted: #707070;        /* gray-50 */
--accent: #ee0000;             /* red-50 — Red Hat Red */
--accent-dark: #a60000;        /* red-60 */
--accent-light: #f56e6e;       /* red-40 */
--tag-border: #c7c7c7;        /* gray-30 · --rh-color-border-subtle-on-light */
--icon-filter: none;                     /* dark icons on light bg (SVGs are dark by default) */
--icon-filter-accent: invert(12%) sepia(100%) saturate(10000%) hue-rotate(0deg) brightness(95%); /* red-50 icons */
```

When using Core Light:
- The ambient glow effect uses a very subtle red tint: `rgba(238,0,0,0.04)`
- Body and slide backgrounds alternate between `--bg-primary` and `--bg-secondary` for rhythm
- Use the **standard** (black wordmark) logo SVG
- Tag pill borders use `--tag-border` (#c7c7c7) with `--text-secondary` text
- The `.accent` tag variant uses `--accent` border and text color (same as dark mode)
- Architecture diagram boxes use `background: rgba(242,242,242,0.8)` and `border: 1px solid #c7c7c7`
- Quote marks use `--accent` at low opacity
- The progress indicator `.current` number is still red-50

**Expressive Dark** (for more colorful content — adds teal and purple accents)
```css
:root { color-scheme: dark; }

--bg-primary: #1b0d33;         /* purple-80 */
--bg-secondary: #000000;       /* black */
--bg-surface: #21134d;         /* purple-70 */
--text-primary: #ffffff;       /* white · --rh-color-text-primary-on-dark */
--text-secondary: #d0c5f4;     /* purple-20 */
--text-muted: #b6a6e9;         /* purple-30 */
--accent: #ee0000;             /* red-50 — Red Hat Red */
--accent-dark: #a60000;        /* red-60 */
--accent-light: #f56e6e;       /* red-40 */
--highlight-teal: #37a3a3;     /* teal-50 */
--highlight-purple: #876fd4;   /* purple-40 */
--tag-border: #3d2785;         /* purple-60 */
--icon-filter: brightness(0) invert(1);  /* white icons on dark bg */
--icon-filter-accent: invert(12%) sepia(100%) saturate(10000%) hue-rotate(0deg) brightness(95%); /* red-50 icons */
```

### Typography
```css
@import url('https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400;500;700;900&family=Red+Hat+Text:wght@400;500;700&family=Red+Hat+Mono:wght@400;700&display=swap');

--font-display: var(--rh-font-family-heading, 'Red Hat Display', sans-serif);   /* Headlines */
--font-body: var(--rh-font-family-body-text, 'Red Hat Text', sans-serif);       /* Body text */
--font-mono: var(--rh-font-family-code, 'Red Hat Mono', monospace);             /* Code, tags, technical */
```

#### Typography Sizing (from `@rhds/tokens`)

Use these token-based sizes for consistent typographic scale across decks:

| Token | Size | Usage |
|-------|------|-------|
| `--rh-font-size-heading-2xl` | 3rem (48px) | Title slide headline |
| `--rh-font-size-heading-xl` | 2.5rem (40px) | Section headlines, big impact text |
| `--rh-font-size-heading-lg` | 2rem (32px) | Slide headlines |
| `--rh-font-size-heading-md` | 1.5rem (24px) | Sub-headlines |
| `--rh-font-size-heading-sm` | 1.25rem (20px) | Card titles, labels |
| `--rh-font-size-body-text-xl` | 1.25rem (20px) | Lead paragraphs, subtitles |
| `--rh-font-size-body-text-lg` | 1.125rem (18px) | Body text on slides |
| `--rh-font-size-body-text-md` | 1rem (16px) | Standard body |
| `--rh-font-size-body-text-sm` | 0.875rem (14px) | Captions, attributions |
| `--rh-font-size-body-text-xs` | 0.75rem (12px) | Tags, breadcrumbs, fine print |

Example usage:
```css
h1 { font-size: var(--rh-font-size-heading-2xl, 3rem); }
h2 { font-size: var(--rh-font-size-heading-lg, 2rem); }
.subtitle { font-size: var(--rh-font-size-body-text-xl, 1.25rem); }
.tag { font-size: var(--rh-font-size-body-text-xs, 0.75rem); }
```

### Visual Effects

The reference screenshot uses a subtle ambient glow in the upper-right corner. Achieve this with a
radial gradient overlay on the slide background:

```css
.slide::before {
  content: '';
  position: absolute;
  top: -20%;
  right: -10%;
  width: 60%;
  height: 60%;
  background: radial-gradient(ellipse, rgba(238,0,0,0.08) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}
```

This creates the distinctive "red atmosphere" effect. Vary the position and opacity per slide for visual
rhythm. On some slides, shift it to the left. On the title slide, make it more prominent.

### Red Hat Logo

Every deck must include the official Red Hat logo. Since these are self-contained HTML files, the logo
is embedded as an inline SVG. The skill provides two versions — use the correct one for the deck's mode.

The logo appears in two places:
1. **Breadcrumb area** (top-left of title slide) — small, subtle, as part of the navigation breadcrumb
2. **Footer / closing slide** — larger, standalone placement

Per brand guidelines:
- On dark backgrounds: hat is red, wordmark is white (reverse full-color)
- On light backgrounds: hat is red, wordmark is black (standard full-color)
- Always maintain minimum spacing around the logo
- Never distort, recolor the hat band, or add effects

#### Logo SVG — Reverse (for Dark Mode)

Use this on dark backgrounds. The hat is red (#e00), the wordmark is white (#fff).
This is the official `RedHat-Logo-A-Reverse` from `static.redhat.com/libs/redhat/brand-assets/2/corp/logo--on-dark.svg`.

```html
<svg class="rh-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 613 145" role="img" aria-label="Red Hat">
  <title>Red Hat</title>
  <path d="M127.47,83.49c12.51,0,30.61-2.58,30.61-17.46a14,14,0,0,0-.31-3.42l-7.45-32.36c-1.72-7.12-3.23-10.35-15.73-16.6C124.89,8.69,103.76.5,97.51.5,91.69.5,90,8,83.06,8c-6.68,0-11.64-5.6-17.89-5.6-6,0-9.91,4.09-12.93,12.5,0,0-8.41,23.72-9.49,27.16A6.43,6.43,0,0,0,42.53,44c0,9.22,36.3,39.45,84.94,39.45M160,72.07c1.73,8.19,1.73,9.05,1.73,10.13,0,14-15.74,21.77-36.43,21.77C78.54,104,37.58,76.6,37.58,58.49a18.45,18.45,0,0,1,1.51-7.33C22.27,52,.5,55,.5,74.22c0,31.48,74.59,70.28,133.65,70.28,45.28,0,56.7-20.48,56.7-36.65,0-12.72-11-27.16-30.83-35.78" fill="#e00"/>
  <path d="M160,72.07c1.73,8.19,1.73,9.05,1.73,10.13,0,14-15.74,21.77-36.43,21.77C78.54,104,37.58,76.6,37.58,58.49a18.45,18.45,0,0,1,1.51-7.33l3.66-9.06A6.43,6.43,0,0,0,42.53,44c0,9.22,36.3,39.45,84.94,39.45,12.51,0,30.61-2.58,30.61-17.46a14,14,0,0,0-.31-3.42Z"/>
  <path d="M579.74,92.8c0,11.89,7.15,17.67,20.19,17.67a52.11,52.11,0,0,0,11.89-1.68V95a24.84,24.84,0,0,1-7.68,1.16c-5.37,0-7.36-1.68-7.36-6.73V68.3h15.56V54.1H596.78v-18l-17,3.68V54.1H568.49V68.3h11.25Zm-53,.32c0-3.68,3.69-5.47,9.26-5.47a43.12,43.12,0,0,1,10.1,1.26v7.15a21.51,21.51,0,0,1-10.63,2.63c-5.46,0-8.73-2.1-8.73-5.57m5.2,17.56c6,0,10.84-1.26,15.36-4.31v3.37h16.82V74.08c0-13.56-9.14-21-24.39-21-8.52,0-16.94,2-26,6.1l6.1,12.52c6.52-2.74,12-4.42,16.83-4.42,7,0,10.62,2.73,10.62,8.31v2.73a49.53,49.53,0,0,0-12.62-1.58c-14.31,0-22.93,6-22.93,16.73,0,9.78,7.78,17.24,20.19,17.24m-92.44-.94h18.09V80.92h30.29v28.82H506V36.12H487.93V64.41H457.64V36.12H439.55ZM370.62,81.87c0-8,6.31-14.1,14.62-14.1A17.22,17.22,0,0,1,397,72.09V91.54A16.36,16.36,0,0,1,385.24,96c-8.2,0-14.62-6.1-14.62-14.09m26.61,27.87h16.83V32.44l-17,3.68V57.05a28.3,28.3,0,0,0-14.2-3.68c-16.19,0-28.92,12.51-28.92,28.5a28.25,28.25,0,0,0,28.4,28.6,25.12,25.12,0,0,0,14.93-4.83ZM320,67c5.36,0,9.88,3.47,11.67,8.83H308.47C310.15,70.3,314.36,67,320,67M291.33,82c0,16.2,13.25,28.82,30.28,28.82,9.36,0,16.2-2.53,23.25-8.42l-11.26-10c-2.63,2.74-6.52,4.21-11.14,4.21a14.39,14.39,0,0,1-13.68-8.83h39.65V83.55c0-17.67-11.88-30.39-28.08-30.39a28.57,28.57,0,0,0-29,28.81M262,51.58c6,0,9.36,3.78,9.36,8.31S268,68.2,262,68.2H244.11V51.58Zm-36,58.16h18.09V82.92h13.77l13.89,26.82H292l-16.2-29.45a22.27,22.27,0,0,0,13.88-20.72c0-13.25-10.41-23.45-26-23.45H226Z" fill="#fff"/>
</svg>
```

#### Logo SVG — Standard (for Light Mode)

Use this on light backgrounds. The hat is red (#e00), the wordmark is near-black (#151515).
This is the official logo extracted from the Red Hat brand standards page header.

```html
<svg class="rh-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 613 145" role="img" aria-label="Red Hat">
  <title>Red Hat</title>
  <path d="M127.47,83.49c12.51,0,30.61-2.58,30.61-17.46a14,14,0,0,0-.31-3.42l-7.45-32.36c-1.72-7.12-3.23-10.35-15.73-16.6C124.89,8.69,103.76.5,97.51.5,91.69.5,90,8,83.06,8c-6.68,0-11.64-5.6-17.89-5.6-6,0-9.91,4.09-12.93,12.5,0,0-8.41,23.72-9.49,27.16A6.43,6.43,0,0,0,42.53,44c0,9.22,36.3,39.45,84.94,39.45M160,72.07c1.73,8.19,1.73,9.05,1.73,10.13,0,14-15.74,21.77-36.43,21.77C78.54,104,37.58,76.6,37.58,58.49a18.45,18.45,0,0,1,1.51-7.33C22.27,52,.5,55,.5,74.22c0,31.48,74.59,70.28,133.65,70.28,45.28,0,56.7-20.48,56.7-36.65,0-12.72-11-27.16-30.83-35.78" fill="#e00"/>
  <path d="M160,72.07c1.73,8.19,1.73,9.05,1.73,10.13,0,14-15.74,21.77-36.43,21.77C78.54,104,37.58,76.6,37.58,58.49a18.45,18.45,0,0,1,1.51-7.33l3.66-9.06A6.43,6.43,0,0,0,42.53,44c0,9.22,36.3,39.45,84.94,39.45,12.51,0,30.61-2.58,30.61-17.46a14,14,0,0,0-.31-3.42Z"/>
  <path d="M579.74,92.8c0,11.89,7.15,17.67,20.19,17.67a52.11,52.11,0,0,0,11.89-1.68V95a24.84,24.84,0,0,1-7.68,1.16c-5.37,0-7.36-1.68-7.36-6.73V68.3h15.56V54.1H596.78v-18l-17,3.68V54.1H568.49V68.3h11.25Zm-53,.32c0-3.68,3.69-5.47,9.26-5.47a43.12,43.12,0,0,1,10.1,1.26v7.15a21.51,21.51,0,0,1-10.63,2.63c-5.46,0-8.73-2.1-8.73-5.57m5.2,17.56c6,0,10.84-1.26,15.36-4.31v3.37h16.82V74.08c0-13.56-9.14-21-24.39-21-8.52,0-16.94,2-26,6.1l6.1,12.52c6.52-2.74,12-4.42,16.83-4.42,7,0,10.62,2.73,10.62,8.31v2.73a49.53,49.53,0,0,0-12.62-1.58c-14.31,0-22.93,6-22.93,16.73,0,9.78,7.78,17.24,20.19,17.24m-92.44-.94h18.09V80.92h30.29v28.82H506V36.12H487.93V64.41H457.64V36.12H439.55ZM370.62,81.87c0-8,6.31-14.1,14.62-14.1A17.22,17.22,0,0,1,397,72.09V91.54A16.36,16.36,0,0,1,385.24,96c-8.2,0-14.62-6.1-14.62-14.09m26.61,27.87h16.83V32.44l-17,3.68V57.05a28.3,28.3,0,0,0-14.2-3.68c-16.19,0-28.92,12.51-28.92,28.5a28.25,28.25,0,0,0,28.4,28.6,25.12,25.12,0,0,0,14.93-4.83ZM320,67c5.36,0,9.88,3.47,11.67,8.83H308.47C310.15,70.3,314.36,67,320,67M291.33,82c0,16.2,13.25,28.82,30.28,28.82,9.36,0,16.2-2.53,23.25-8.42l-11.26-10c-2.63,2.74-6.52,4.21-11.14,4.21a14.39,14.39,0,0,1-13.68-8.83h39.65V83.55c0-17.67-11.88-30.39-28.08-30.39a28.57,28.57,0,0,0-29,28.81M262,51.58c6,0,9.36,3.78,9.36,8.31S268,68.2,262,68.2H244.11V51.58Zm-36,58.16h18.09V82.92h13.77l13.89,26.82H292l-16.2-29.45a22.27,22.27,0,0,0,13.88-20.72c0-13.25-10.41-23.45-26-23.45H226Z" fill="#151515"/>
</svg>
```

#### Logo CSS

```css
.rh-logo {
  height: 28px;
  width: auto;
}
.rh-logo.small { height: 20px; }
.rh-logo.large { height: 40px; }
```

#### Logo Placement Rules

**Title slide**: Place the logo in the breadcrumb row, left-aligned, before any breadcrumb text:
```html
<div class="breadcrumb">
  <svg class="rh-logo small" ...>[logo SVG]</svg>
  <span style="margin-left: 12px;">› NAPS STP</span>
</div>
```

**Closing / CTA slide**: Place the logo centered or left-aligned near the bottom of the slide,
above or beside the attribution, at `.rh-logo.large` size.

**Every other slide**: The logo should NOT appear on every content slide — this avoids clutter.
Instead, include a minimal red accent bar or the Red Hat red (#ee0000) in the progress indicator
to maintain brand presence throughout.

### Red Hat Icons

Red Hat publishes an official icon library (`@rhds/icons`) with 1,135 SVGs across 4 sets. Use ` ` tags
pointing to the jsDelivr CDN to add icons to slides. Icons are controlled via CSS `filter` variables
so they adapt to each color mode automatically.

**CDN URL pattern:**
```
https://cdn.jsdelivr.net/npm/@rhds/icons@2.1.0/{set}/{icon}.svg
```

#### Choosing Icons — Read `references/rhds-icons.md`

**Before using any icon, always read `references/rhds-icons.md`** — it is the single source of truth for:
- The full inventory of all 1,135 icons across 4 sets (`standard`, `ui`, `microns`, `social`)
- **Common alias mappings** — many intuitive names don't match the actual RHDS names (e.g., `database` → `data`, `integration` → `interoperability`, `build` → `circuit`, `network` → `network-automation`)
- **Semantic groupings** by topic (Cloud, Security, AI, DevOps, etc.) to quickly find the right icon for a slide's subject matter

Do **not** guess icon names. If you use a name that doesn't exist in the inventory, the icon will silently fail to load.

#### Icon CSS

```css
/* === ICON STYLES === */
.rh-icon {
  height: 48px;
  width: 48px;
  filter: var(--icon-filter);
  vertical-align: middle;
}
.rh-icon.small  { height: 24px; width: 24px; }
.rh-icon.medium { height: 48px; width: 48px; }
.rh-icon.large  { height: 64px; width: 64px; }
.rh-icon.xl     { height: 96px; width: 96px; }
.rh-icon.accent { filter: var(--icon-filter-accent); }
```

#### Icon Usage in HTML

```html
<!-- Basic icon -->
<img class="rh-icon" src="https://cdn.jsdelivr.net/npm/@rhds/icons@2.1.0/standard/cloud.svg" alt="Cloud">

<!-- Small accent-colored icon beside a headline -->
<h2><img class="rh-icon small accent" src="https://cdn.jsdelivr.net/npm/@rhds/icons@2.1.0/standard/shield.svg" alt=""> Security First</h2>

<!-- Large icon for a stat slide -->
<img class="rh-icon xl accent" src="https://cdn.jsdelivr.net/npm/@rhds/icons@2.1.0/standard/graph-line-up.svg" alt="">
<div class="big-number">3.2x</div>
```

#### Icon Usage Guidelines

- **Use sparingly**: 2-3 icons per slide maximum. Icons should clarify, not decorate.
- **Best uses**: Stat slide topic icons, feature list bullets, architecture diagram box labels, comparison column headers.
- **Don't**: Use icons as the sole content, mix too many sizes on one slide, use icons without supporting text.
- **Sizing**: Use `.small` (24px) inline with text, `.medium` (48px) for feature lists, `.large`/`.xl` for hero/stat accent.
- **Color**: Icons inherit the mode's filter by default. Use `.accent` class sparingly for emphasis (same restraint as red-50 text).

### Spacing Scale (from `@rhds/tokens`)

Use the official Red Hat spacing tokens for all padding, margins, and gaps. This ensures visual
consistency with the broader Red Hat design system. All values are multiples of 4px.

| Token | Value | Common Usage |
|-------|-------|-------------|
| `--rh-space-xs` | 4px | Tight inline gaps, icon-to-text spacing |
| `--rh-space-sm` | 8px | Compact element spacing |
| `--rh-space-md` | 16px | Standard element spacing, tag padding horizontal |
| `--rh-space-lg` | 24px | Section gaps, card padding |
| `--rh-space-xl` | 32px | Slide content gaps |
| `--rh-space-2xl` | 48px | Major section spacing |
| `--rh-space-3xl` | 64px | Slide side padding |
| `--rh-space-4xl` | 80px | Slide top/bottom padding |
| `--rh-space-5xl` | 96px | Large hero spacing |
| `--rh-space-6xl` | 112px | Extra large spacing |
| `--rh-space-7xl` | 128px | Maximum spacing |

Example usage:
```css
.slide { padding: var(--rh-space-4xl, 80px) var(--rh-space-3xl, 64px); }
.content-body { gap: var(--rh-space-lg, 24px); }
.breadcrumb svg + span { margin-left: var(--rh-space-sm, 8px); }
```

### Border & Shadow Tokens (from `@rhds/tokens`)

```css
/* Border widths */
--rh-border-width-sm: 1px;    /* Default borders, tag outlines */
--rh-border-width-md: 2px;    /* Emphasized borders, accent lines */
--rh-border-width-lg: 3px;    /* Heavy emphasis, decorative rules */

/* Border radii */
--rh-border-radius-sharp: 0px;       /* No rounding — architecture boxes */
--rh-border-radius-default: 3px;     /* Subtle rounding — cards, surfaces */
--rh-border-radius-pill: 64px;       /* Full pill — tags, badges */

/* Box shadows — use for elevated surfaces and architecture diagram depth */
--rh-box-shadow-sm: 0 2px 4px 0 rgba(21, 21, 21, 0.2);      /* Subtle lift */
--rh-box-shadow-md: 0 4px 6px 1px rgba(21, 21, 21, 0.25);    /* Cards */
--rh-box-shadow-lg: 0 6px 8px 2px rgba(21, 21, 21, 0.3);     /* Modals, panels */
--rh-box-shadow-xl: 0 8px 24px 3px rgba(21, 21, 21, 0.35);   /* Hero elements */
```

### Video Container Styling

```css
/* === VIDEO CONTAINER === */
.video-container {
  position: relative;
  width: 100%;
  max-width: 960px;
  aspect-ratio: 16 / 9;
  border-radius: var(--rh-border-radius-default, 3px);
  overflow: hidden;
  box-shadow: var(--rh-box-shadow-lg, 0 6px 8px 2px rgba(21, 21, 21, 0.3));
  background: var(--bg-secondary);
  align-self: center;
}
.video-container iframe,
.video-container video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: none;
}
```

### Media Container Styling (Memes, GIFs, Linked Images)

```css
/* === MEDIA CONTAINER === */
.media-container {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  width: 100%;
  max-height: 65vh;
  padding: var(--rh-space-md, 16px) 0;
  align-self: center;
}
.slide-media {
  display: block;
  max-width: 90%;
  max-height: 100%;
  object-fit: contain;
  border-radius: var(--rh-border-radius-default, 3px);
  box-shadow: var(--rh-box-shadow-lg, 0 6px 8px 2px rgba(21, 21, 21, 0.3));
}
.media-caption {
  font-family: var(--rh-font-family-body-text, 'Red Hat Text', sans-serif);
  font-size: var(--rh-font-size-body-text-lg, 1.125rem);
  color: var(--text-secondary);
  text-align: center;
  margin-top: var(--rh-space-md, 16px);
  max-width: 720px;
  align-self: center;
}
```

### Tag / Pill Styling

The reference uses outlined pills for categorization (e.g., "Local-First", "Air-Gap Ready"). Style them
using design tokens for sizing, spacing, and borders:

```css
.tag {
  display: inline-block;
  padding: var(--rh-space-xs, 4px) var(--rh-space-md, 16px);
  border: var(--rh-border-width-sm, 1px) solid var(--tag-border);
  border-radius: var(--rh-border-radius-pill, 64px);
  font-family: var(--font-mono);
  font-size: var(--rh-font-size-body-text-xs, 0.75rem);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.tag.accent {
  border-color: var(--accent);
  color: var(--accent);
}
```

