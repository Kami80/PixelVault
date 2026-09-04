# PixelVault V5.3 — Duration-aware Planner

## Planner timeline
- Rebuilt Daily Planner as a true time-block timeline.
- Rebuilt Weekly Planner as a seven-day time-grid instead of stacked cards.
- Task blocks now automatically scale to their estimated duration. A 240-minute task occupies four hours of timeline space.
- Timeline automatically extends earlier/later when scheduled work falls outside configured working hours.
- Overlapping tasks are arranged side-by-side rather than visually covering each other.
- Current-time indicator is shown on today's timeline.
- Scheduled-but-unslotted tasks have a dedicated Anytime row.
- Calendar task chips now show duration.

## Scheduling UX
- Dragging onto Daily/Weekly timelines schedules to the exact drop position.
- Time drops snap to 15, 30 or 60 minute increments.
- Added planner zoom controls to change vertical hour spacing.
- Dragging into Anytime removes the start time while keeping the date.
- Dragging into Planning Inbox unschedules the task completely.
- Improved horizontal scrolling and readability for the weekly grid.

## Task quick actions
- Added planner task action menu.
- Duplicate task.
- Move to tomorrow.
- Move to today.
- Unschedule.
- Complete/reopen.
- Open full task details.
- Duplicate is also available from the Task Detail screen.
- Duplicates preserve project, date, start time, duration, tags and notes but reset completion/recurrence state.

## Compatibility
- Added persistent planner snap and timeline zoom preferences to `UserSettings`.
- Run `python manage.py migrate` after copying the V5.3 files.
