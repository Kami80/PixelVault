# PixelVault V5.1 — Forms, Contrast & Save Flow

This update focuses on the UI issues found during real use of the Django edition.

## Navigation & responsive shell

- Fixed truncated sidebar labels such as `HO…`, `ID…`, and `PR…` by removing the legacy fixed width inherited by navigation text.
- Navigation labels now wrap/read normally and retain their counters.
- The sidebar has one controlled scroll area while the local system card remains safely anchored at the bottom.
- Added a proper mobile sidebar backdrop and safer mobile width/spacing.
- Improved navigation target sizes and label contrast.

## Readability & themes

- Strengthened muted-text contrast in every dark and light theme.
- Removed inappropriate dark text shadows from light themes.
- Reworked status and chip colors to use the active theme's semantic palette instead of old hard-coded dark-theme colors.
- Increased form labels, inputs, helper copy, buttons, metadata and utility text.
- Improved placeholder, select-option and focus-state readability.

## Forms

- Rebuilt Idea, Project, Task and Skill create/edit forms around numbered sections and clearer hierarchy.
- Added larger 50px controls, clearer required-field treatment and stronger focus states.
- Added field-level helper text and better descriptions.
- Added a prominent pin control to object forms.
- Removed the nested/double-scroll behavior from the old form dialog.
- Forms now have a single internal scroll area with a stable header and action footer.
- Added unsaved-change confirmation when cancelling or closing a changed form.
- Save buttons enter a visible `SAVING TO DJANGO…` state and cannot be double-submitted.

## Confirmed save workflow

- Create/edit changes are now treated as successful only after the Django state endpoint confirms the write.
- A failed save rolls the in-memory object back and leaves the form available for correction/retry.
- Successful saves close the form automatically.
- The newly created or edited object is immediately opened after saving:
  - Ideas open in a dedicated readable detail view.
  - Projects open in their full Project Workspace.
  - Tasks open in a dedicated readable detail view.
  - Skills open directly in the Skill editor.
- Added success banners and richer success/error toast notifications.
- Idea → Project conversion now uses the same confirmed-save behavior and opens the resulting project.
- Skill editor saves now wait for Django confirmation before reporting success.

## Empty states

- Replaced the plain Projects empty screen with a guided first-project onboarding state explaining project identity, local folder connection and execution flow.

No database schema changes are required for V5.1.
