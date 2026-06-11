
- Updated bot_avatar rendering logic to use manager base url.
- Removed legacy chat command/tool compatibility; the plugin now accepts only explicit workflow IDs.
- Refactored ncqq entrypoints to compiled internal workflows instead of direct command dispatch.
- Aligned workflows with ncqq-manager router capabilities, including health, BotShepherd, bot runtime, messages, audit, resources, and config snapshot read workflows.
- Reworked workflows from scattered capability entries into one-direction business flows:
  create_instance, relogin_instance, control_instance, connect_backend,
  check_instance, list_instances, check_manager, delete_instance, etc.
- Added integrated create approval handling so non-admin create requests can create,
  bind, and optionally inject a backend from one approval.
