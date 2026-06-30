# Dark Dashboard UI Design

## Goal

Restyle Passport Auth's web UI to feel like a dark-mode version of the provided Cursor/Mobbin reference. The change should apply across the authenticated dashboard, login, setup/onboarding, admin invite, and hosted auth pages.

## Visual Direction

- Use a quiet, dark admin-app theme with matte black and charcoal surfaces.
- Keep typography compact and utilitarian with the existing SF/Avenir-style font stack.
- Use muted gray copy, thin borders, 8px radii, and low-contrast card backgrounds.
- Remove the current dramatic grid and glow treatment from the app background.
- Use restrained green only for positive/status accents.
- Avoid exact layout copying; borrow spacing, sidebar treatment, button shape, card density, and information hierarchy.

## Shell And Navigation

- Keep the existing two-column app shell, but tune it closer to the reference:
  - A wider, soft dark sidebar with minimal border separation.
  - Compact brand and profile blocks.
  - Nav items as filled muted rows on active/hover states.
  - Existing route icons rendered beside nav labels where practical.
- Keep the current topbar, but make it quieter and aligned with the restyled content surface.

## Components

- Cards and panels use one shared surface language: dark charcoal, subtle border, no decorative gradients.
- Buttons use compact rectangular styling with 7-8px radius:
  - Primary buttons use light foreground-on-dark or brand accent depending on context.
  - Secondary buttons use dark fill with border.
- Inputs, selects, textareas, toggles, tables, chips, dialogs, and template previews adopt the same density and dark contrast.
- Existing content structure and data flows remain unchanged.

## Page Coverage

- Dashboard: compact hero, metric cards, and operations rows restyled.
- Analytics: metrics, retention cards, method rows, and recent events restyled.
- Users/Admins: table panels, rows, search, invite form, and edit dialog restyled.
- Settings/Templates: section cards, form fields, toggles, template editor, and email preview frames restyled.
- Auth/Login/Onboarding/Hosted auth: cards and forms restyled to match the dashboard rather than feeling like a separate product.

## Implementation Notes

- Primary implementation should stay in `apps/web/styles.css`.
- `apps/web/app.js` can receive small markup changes where needed, especially nav icons.
- `apps/web/index.html` cache-bust version should be updated with a new UI version string.
- No API behavior changes are expected.

## Verification

- Run focused dashboard/static UI tests after changes.
- Run the broader API test suite if feasible.
- Start a local static server or app server and inspect the UI manually across dashboard/auth surfaces.
