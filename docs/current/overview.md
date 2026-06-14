
- Updated bot_avatar rendering logic to use manager base url.
- Removed legacy chat command/tool compatibility; the plugin now accepts only explicit workflow IDs.
- Refactored ncqq entrypoints to compiled internal workflows instead of direct command dispatch.
- Aligned workflows with ncqq-manager router capabilities, including health, BotShepherd, bot runtime, messages, audit, resources, and config snapshot read workflows.
- Reworked workflows from scattered capability entries into one-direction business flows:
  create_instance, relogin_instance, control_instance, connect_backend,
  check_health, check_instance, list_instances, delete_instance, etc.
- Added `check_health` as the user-facing aggregated health workflow so general
  health/status questions do not need several separate workflow calls.
- Hid the narrower health diagnostics from user-facing workflow lists; use
  `check_health detail` when detailed manager/BotShepherd/Bot runtime diagnosis is needed.
- Added integrated create approval handling so non-admin create requests can create,
  bind, and optionally inject a backend from one approval.
- Optimized QQ group approval UX: high-privilege requests now send real At
  mentions to AstrBot admins and support approve/reject by direct ID reply or
  by quoting the bot approval notice.
- Tightened approval safety: quoted approvals must include a parsable approval
  ID in the quoted message; the plugin no longer guesses from the group's only
  pending task.
- Approval handling now uses strict leading approve/reject commands and atomic
  queue claiming to prevent ambiguous text and duplicate execution.
- Admin checks are unified through AstrBot role state plus configured
  `admins_id`; admins read pending tasks through Astr instead of extra push
  delivery.
- `review_approvals` now supports list/approve/reject, so admins can process
  pending tasks through Astr without relying on group reply shortcuts.
- Added optional group response whitelist. When enabled, group messages outside
  `response_groups` are ignored by the LLM tool, `/ncqq` command, and approval
  shortcut listener; private chat remains available.
- Aggregated health checks now preserve backend endpoint read failures instead
  of reporting them as an empty endpoint list.
- Synced hot-reload fixes from the deployed instance: workflow tool docstring
  parameters now use AstrBot's `name(type): description` format, and config
  schema types now use `bool` / `int`.
- Reorganized runtime code into `core/`, `tools/`, `workflows/`, and
  `rendering/`.
- Added main workflow routing for chat usage: `manage_instance`, `query`, and
  `manage_backend`; detailed workflows remain directly callable as internal
  targets.
- Split the oversized workflow implementation into focused modules under
  `workflows/` while keeping `workflows` as the stable public API.
- Added architecture handoff docs in `docs/architecture.md`,
  `docs/module-map.md`, and function-named architecture docs for future
  model-assisted maintenance.
- Added AstrBot plugin compliance notes in `docs/plugin-compliance.md`.
- Replaced root `logo.png` with a generated 256x256 transparent flat mascot
  icon showing AstrBot and ncqq mascots hugging.
- Synced plugin metadata with latest AstrBot docs: `short_desc`,
  `astrbot_version`, `support_platforms`, and explicit API imports.
- Added `requirements.txt` for the external `aiohttp` runtime dependency.
- Added `.gitignore` for Python caches, logs, and local virtualenvs; removed
  tracked Python bytecode from the archive.
