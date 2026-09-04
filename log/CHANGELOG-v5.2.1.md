# PixelVault V5.2.1 — Planner Core Fix

## Fixed
- Fixed the V5 Planner entering **RECOVERY MODE** during normal startup.
- Restored the date/time utility layer accidentally omitted from V5 `app.js`:
  - `dateShift()`
  - `monthStart()`
  - `monthEnd()`
  - `weekStartOf()`
  - `rangeDates()`
  - `parseTime()`
- Weekly Planner now resolves the correct week range for both Monday-first and Sunday-first workspaces.
- Calendar month grids can generate their 42-day view without throwing a ReferenceError.
- Daily/weekly task sorting by start time now works safely, including unslotted tasks.
- Project due-soon calculations and report date ranges now use the same restored date utilities.
- Date-only calculations use local noon to reduce DST-related day-shift bugs.
- Invalid/empty task times are handled safely instead of breaking rendering.

## Compatibility
- This is a frontend core fix. No new migration is required beyond the existing V5.2 GitHub Pages migration if you are using V5.2.
