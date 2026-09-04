# PixelVault V5.5 — Sidebar UX Rebuild

## Fixed
- `menu-toggle` now works on desktop and mobile.
- Desktop: menu button collapses/expands the sidebar and persists the choice.
- Mobile/tablet: menu button opens/closes the navigation drawer with a backdrop.
- Sidebar state and ARIA attributes stay synchronized after resize and page changes.
- `Esc` closes the mobile drawer.
- Added `Ctrl+B` keyboard shortcut to toggle the sidebar.

## Sidebar UX enhancements
- New custom WEBP navigation icons across the entire sidebar.
- Larger, clearer navigation targets and stronger active states.
- Full-width Quick Create action at the top of the sidebar (`N` shortcut).
- Workspace / Knowledge & Review navigation groups.
- Live item-count badges for Ideas, Projects, Tasks, Skills and Notes.
- Improved Quick Access controls for Pinned, Today and Overdue.
- Persistent desktop collapsed mode with hover/focus tooltips.
- Better mobile drawer width, scrolling and backdrop behavior.
- Improved profile/system card; clicking it opens Settings.
- Added keyboard shortcut hints inside the expanded sidebar.
- Better light-theme contrast.
- Sidebar no longer clips labels, badges, icons or the profile footer.

## Icon integration
- Uses the new transparent WEBP icons for Home, Ideas, Projects, Tasks, Planner, Skills, Reports, Notes and Settings.
- Topbar Notes/Settings buttons use the same icon language.
- Mobile dock uses the WEBP icons.
- Home icon ribbon and create/entity UI reuse the same assets for visual consistency.

## Files changed
- `templates/pixelvault/app.html`
- `static/pixelvault/css/styles.css`
- `static/pixelvault/js/app.js`
- `static/pixelvault/assets/nav-*.webp`

No database migration is required for V5.5.
