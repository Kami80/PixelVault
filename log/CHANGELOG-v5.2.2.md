# PixelVault V5.2.2

- Fixed Kanban column headers covering task cards while scrolling.
- Rebuilt task-board column/body layout for cleaner drag-and-drop and responsive behavior.
- Added `Idea.live_site_url` to Django with migration `0003_idea_live_site_url`.
- Added Live Site URL to Idea create/edit forms, cards and Idea Detail.
- Added one-click LIVE SITE opening from Ideas.
- Idea → Project conversion now carries the Idea live URL into the project GitHub Pages URL.
- Backup/state serialization now preserves Idea live-site URLs.
