# Dark Dashboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle all Passport Auth web UI surfaces as a dark, compact admin interface inspired by the provided Cursor/Mobbin reference.

**Architecture:** Keep the existing static app architecture intact. Apply the shared visual system primarily through CSS tokens and component classes, with small `app.js` template changes only where markup needs icons or better shell structure.

**Tech Stack:** Static HTML, vanilla JavaScript templates, CSS, FastAPI static asset tests with pytest.

---

## File Structure

- Modify `apps/web/styles.css`: theme tokens, shell/sidebar, cards, buttons, forms, tables, dialogs, onboarding, hosted auth, analytics, and responsive styling.
- Modify `apps/web/app.js`: add nav icons to sidebar links using the existing `routeMeta` and `renderRouteIcon()` helpers.
- Modify `apps/web/index.html`: update the cache-bust UI version string.
- Modify `apps/api/tests/test_dashboard_ui.py`: update the expected cache-bust version and add static checks for the dark reference styling.

### Task 1: Static UI Contract Tests

**Files:**
- Modify: `apps/api/tests/test_dashboard_ui.py`

- [ ] **Step 1: Add assertions for the new UI contract**

Add checks that `styles.css` contains the dark shell/card/sidebar tokens and that `app.js` renders route icons in the primary nav. Update the cache-bust version expected in `index.html` to `2026-06-30-dark-admin-ui`.

- [ ] **Step 2: Run focused tests and verify they fail before implementation**

Run: `python -m pytest apps/api/tests/test_dashboard_ui.py -q`

Expected before implementation: at least one assertion fails for the new version string or nav icon markup.

### Task 2: Dark Reference Theme CSS

**Files:**
- Modify: `apps/web/styles.css`

- [ ] **Step 1: Replace global tokens and background treatment**

Set dark matte tokens for `--void`, `--plane`, `--line`, text colors, and `--signal`. Remove the current grid/radial page background in favor of a flat charcoal app background.

- [ ] **Step 2: Restyle shell, sidebar, nav, and topbar**

Use a wider sidebar, compact profile block, muted active nav row, route icons, and a quiet sticky topbar.

- [ ] **Step 3: Restyle shared components**

Apply the new surface language to `.auth-card`, `.panel`, `.overview-card`, `.metric`, `.form-panel`, `.settings-section`, `.step-rail`, `.onboarding-main`, buttons, fields, toggles, chips, table panels, rows, dialogs, and template cards.

- [ ] **Step 4: Tighten page-specific layouts and responsive rules**

Keep existing data and content structure while reducing oversized hero typography, spacing, and decorative treatments across dashboard, analytics, users, admins, settings, templates, auth, onboarding, and hosted auth.

### Task 3: Sidebar Icon Markup And Cache Bust

**Files:**
- Modify: `apps/web/app.js`
- Modify: `apps/web/index.html`

- [ ] **Step 1: Render route icons inside primary nav links**

In `renderAppShell()`, include `${renderRouteIcon(routeMeta[route.href]?.icon || "home")}` before each nav label.

- [ ] **Step 2: Update static asset version**

Change every `2026-06-26-toggle-ui` string in `apps/web/index.html` to `2026-06-30-dark-admin-ui`.

### Task 4: Verification

**Files:**
- Test: `apps/api/tests/test_dashboard_ui.py`

- [ ] **Step 1: Run CSS syntax/static checks**

Run: `git diff --check`

Expected: exit code 0.

- [ ] **Step 2: Run focused dashboard UI tests**

Run: `python -m pytest apps/api/tests/test_dashboard_ui.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run broader API test suite if dependencies are available**

Run: `python -m pytest apps/api/tests -q`

Expected: all tests pass, or report dependency/environment failures exactly.

- [ ] **Step 4: Start a local static server for manual inspection**

Run: `python -m http.server 5173 --directory apps/web`

Expected: the UI is available at `http://localhost:5173`.
