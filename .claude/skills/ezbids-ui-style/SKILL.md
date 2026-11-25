---
name: ezbids-ui-style
description: Use when changing anything users see in ui/ or electron/ (colours, fonts, layout, the logo or header, landing page copy, links to other sites, dialogs, credits or acknowledgements), or the aimport QA viewer pages.
---

# ezBIDS UI style

The web converter, the landing page and the desktop app share one look: brainlife-lite.

## Rules

1. **Tokens come from `ui/src/theme.css` only.** Never hard-code a colour, font or radius in a component; add a variable there if one is missing.
2. **Brand lockup is `ui/src/components/brand/BrandLockup.vue`** (brainlife.io mark, "ezBIDS" over "by brainlife.io"). Use the component; never redraw it. The brainlife.io logo stays visible on every page and in the QA viewer (`aimport/src/aimport/viewer.py` `brand_header`).
3. **No external windows.** Links to other sites open in `ExternalPageDialog` (`ui/src/externalPage.ts` `openExternal`; plain `<a href>` is intercepted by `interceptExternalLinks`). Desktop: every https page shows in a locked-down `<webview>` (`electron/inAppBrowsing.ts`). Web: hosts that forbid framing get a dialog that opens a new tab only after the user confirms. Add a host to `FRAMEABLE_HOSTS` only after `curl -sI` shows no `X-Frame-Options` / `frame-ancestors`.
4. **Copy:** ezBIDS converts *neuroscience data (neurophysiology, neuroimaging and microscopy)*, not "MRI data" or "neuroimaging data".
5. **Credits:** always "The University of Texas at Austin", capital *The*, also mid-sentence.
6. **Show screenshots** (web and desktop when both change) in the PR body; keep them in `docs/<topic>/`.
7. Check with `cd ui && npx vite build` and, for desktop changes, `cd electron && npx tsc --noEmit`.

## Quick reference

| Token | Value |
|---|---|
| Primary | `#3d6a92` (`--el-color-primary`) |
| Success / warning / danger / info | `#5fa86b` / `#c9a94f` / `#d0494f` / `#3b9fd0` (brainlife-lite `statusColors`) |
| Text / secondary text | `#2d3748` / `#718096` |
| Page / nav / panel background | `#f5f5f5` / `#fafafa` / `#ffffff` |
| Font | DM Sans (Geist on the landing page), weights 300/500, headings not bold |
| Radius | 6px panels (`--panel-radius`), 4px controls |
| Lockup colours | "ez" `#3b9fd0`, "BIDS" `#1d2230` (`#eef3f6` on dark), "by brainlife.io" `#718096` |

## Common mistakes

- `window.open(...)`, `target="_blank"` or `shell.openExternal` for an outside link (one `target="_blank"` remains in `ui/src/features/aimport/AimportPage.vue`; do not copy it).
- A second copy of the logo/lockup markup, or hiding the logo on a "focused" page.
- Element Plus defaults (blue `#409eff`, 4px panel corners) leaking through because a component set its own colour.
- "the University of Texas at Austin" (lower-case *the*) or "UT Austin" in credits.
- A UI PR with no screenshot.
