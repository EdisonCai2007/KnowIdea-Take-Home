# KnowIdea Theme Map

Captured from:

- https://www.knowidea.dev/
- https://www.knowidea.dev/about
- https://www.knowidea.dev/product
- https://www.knowidea.dev/press-releases
- Supplemental check: https://www.knowidea.dev/careers

## Summary

KnowIdea uses a polished executive-AI theme: dark, high-contrast "predictive intelligence" pages for brand, about, and press; light, warm product/documentation pages for framework and careers content. The shared identity is a fixed glass pill navigation bar, Poppins-led typography, large airy spacing, purple as the main intelligence/accent color, and subtle data-interface motifs such as grids, dots, glows, charts, and diagram cards.

It is not a compact dashboard theme. It is spacious, cinematic, and easier on the eyes, with dense content only inside cards, diagrams, press grids, and framework modules.

## Color System

The strongest CSS token source is `.landing-v2` in `http/css/chunk-theme.css`.

| Role | Token | Hex / value | Use |
| --- | --- | --- | --- |
| Light page base | `--bg-deep` | `#f7f5f2` | Product and careers page canvas |
| Paper surface | `--v2-surface` | `#fdf9f1` | Light cards and panels |
| Paper secondary | `--bg-paper` | `#efebe6` | Tags, soft background blocks |
| Primary ink | `--v2-text` | `#1a1530` | Light-page headings and primary copy |
| Secondary ink | `--v2-text-2` | `#2e2845` | Secondary text and labels |
| Muted ink | `--v2-text-3` | `#5a5470` | Body/supporting text |
| Soft muted ink | `--v2-text-4` | `#8b859d` | Eyebrows, placeholders, faint labels |
| Main accent | `--v2-accent` | `#6d28d9` | Purple emphasis, links, active states |
| Accent bright | `--v2-accent-2` | `#7c3aed` | Gradients, focus rings, hover states |
| Accent magenta | `--v2-accent-3` | `#c026d3` | Occasional vivid gradient accents |
| Accent surface | `--v2-accent-soft` | `#f3edff` | Pills, badges, soft purple fills |
| Success | `--v2-green` | `#047857` | Status dots, verified/security notes |
| Gold accent | `--v2-gold` | `#b45309` | Highlight badges |
| Light border | `--v2-border` | `#1a15301a` | Light card borders |
| Soft border | `--v2-border-soft` | `#1a15300f` | Dividers and weak panel borders |

Dark pages add a separate atmospheric palette:

| Role | Value | Use |
| --- | --- | --- |
| Near-black | `#08060e`, `#09090b`, `#0a0818`, `#0f0c22` | Page and header base |
| Deep indigo | `#14102c`, `#16122b`, `#1a1232` | Main dark gradients |
| Purple slate | `#2a2050`, `#5a5088`, `#8a84b8`, `#b0aed0` | Hero glow ramps |
| White text | `#ffffff`, `rgba(255,255,255,0.88)`, `rgba(255,255,255,0.6)` | Dark headings, nav, secondary copy |
| Press card body | `rgba(28,24,42,0.9)` to `rgba(20,17,32,0.95)` | Press release cards |

## Typography

- Primary rendered font: `Poppins, sans-serif, Arial, system-ui, sans-serif`.
- Secondary rendered font on About and Press supporting copy: `googleSans, "googleSans Fallback", sans-serif, Arial, sans-serif`.
- Preloaded font assets include GoogleSans Regular, Medium, SemiBold, Bold and Telegraf Regular/UltraBold.
- The public CSS maps some decorative aliases back to Poppins: `--font-instrument-serif`, `--font-jetbrains-mono`, and `--font-telegraf` are set to `var(--font-poppins)` inside `.landing-v2`.
- Heading style is large, light-to-medium weight, tight letter spacing:
  - Dark H1 examples: 60-72px, weight 500, line-height about 1.0.
  - Light product H2 examples: 44px or 56px, weight 300, line-height about 1.05.
  - Cards: 20-30px headings, weight 500-600.

## Layout And Spacing

- Header: fixed, centered, max width around 1200px, pill radius `999px`, 8px horizontal action gap, compact 15px navigation.
- Main containers: usually max width 5xl to 1280px depending page type.
- Dark pages: full-bleed gradient/grid backgrounds with centered hero copy and large vertical breathing room.
- Light pages: off-white background, left-aligned product sections, large diagram frames, and soft bordered cards.
- Press page: dark editorial grid, one large featured card followed by two-column article cards.
- Careers page: light page with centered hero and a large rounded white job card.

## Components

### Glass Header

The header is the strongest reusable motif:

- Background: `rgba(8,6,14,0.72)`.
- Border: `1px solid rgba(255,255,255,0.08)`.
- Filter: `backdrop-filter: blur(22px) saturate(160%)`.
- Shadow: `0 8px 32px rgba(0,0,0,0.28)` plus a faint inset white highlight.
- CTAs: ghost sign-in text on transparent, and a white pill "Get your edge" button with dark ink.

### Buttons And Pills

- Primary nav CTA: white fill, `#1a1530` text, `999px` radius, 48px height.
- Accent pill: `#f3edff` fill, purple text `#6d28d9`, border `rgba(124,58,237,0.3)`.
- Small controls use 8px radius; major navigation and badges use full pills.

### Cards

- Press cards: dark gradient surfaces, `16px` radius, white/8 border, large image area, hover image scale.
- Product cards: cream/white surfaces, soft ink borders, 14-16px radius, light shadows.
- Framework modules use three semantic accent colors: purple for Understand, rose `#be185d` for Predict, green `#047857` for Decide.

### Backgrounds

- Dark backgrounds combine radial dots, subtle grids, and purple/indigo radial glows.
- Product backgrounds are warm off-white with purple accent gradients used sparingly.
- Home uses a cinematic full-viewport visual/video treatment under the same glass nav.

## Implementation Notes

- The site is a prerendered Next.js app. Headers include `x-nextjs-prerender: 1` and `x-nextjs-stale-time: 300`.
- HTML uses Tailwind-style utility classes plus custom `v2-*` classes.
- Source and CSS captures are in `http/`.
- Rendered computed-style data is in `rendered-analysis.json`.
- The three CSS chunks are saved under `http/css/`.

## Screenshot References

Viewport captures are best for top-of-page design reference. Full-page captures are also included, but fixed headers and animated sections can repeat in the stitched full-page output.

| Page | Viewport | Full page |
| --- | --- | --- |
| Home | `screenshots/home-desktop-viewport.jpg` | `screenshots/home-desktop-full.jpg` |
| About | `screenshots/about-desktop-viewport.jpg` | `screenshots/about-desktop-full.jpg` |
| Product | `screenshots/product-desktop-viewport.jpg` | `screenshots/product-desktop-full.jpg` |
| Press releases | `screenshots/press-releases-desktop-viewport.jpg` | `screenshots/press-releases-desktop-full.jpg` |
| Careers | `screenshots/careers-desktop-viewport.jpg` | `screenshots/careers-desktop-full.jpg` |

## Usage Guidance

Use the dark treatment for brand, authority, press, and executive-intelligence moments. Use the light treatment for product explanation, hiring, documentation, and framework diagrams. Keep the nav compact and glassy across both modes so the experience still feels like one product.

