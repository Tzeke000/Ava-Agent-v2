# Ava Tools Roadmap
**Last updated:** April 28, 2026

## Tool Tiers

- **Tier 1 (autonomous):** Ava may run without prior permission.
- **Tier 2 (verbal check-in):** Ava narrates intent, then executes.
- **Tier 3 (explicit yes):** Ava requires direct user approval before execution.

## Current Tools

### Tier 1 — Built

- **Name:** `web_search`  
  **Description:** Search the web for fresh information.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Checking current events, package updates, docs changes.  
  **Example:** "I should quickly check if that API changed this month."

- **Name:** `web_fetch`  
  **Description:** Fetch and read webpage content for analysis.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Pulling exact text from docs and release notes.  
  **Example:** "I'll open the official migration page and summarize the steps."

- **Name:** `read_file`  
  **Description:** Read local files in the project.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Understanding code before edits, reviewing logs/config.  
  **Example:** "Let me read the operator server file first."

- **Name:** `list_files`  
  **Description:** Enumerate files/directories in allowed paths.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Discovering project structure and locating targets.  
  **Example:** "I’ll list docs to find the roadmap files."

- **Name:** `search_files`  
  **Description:** Search repository contents by pattern.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Finding callsites, symbols, and endpoint usage.  
  **Example:** "I’ll search where TTS gets invoked after replies."

- **Name:** `memory_query`  
  **Description:** Query Ava memory artifacts/context stores.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Continuity recall and context-sensitive reasoning.  
  **Example:** "I want to pull what we learned about this user before."

- **Name:** `note_self`  
  **Description:** Record internal notes for continuity/self-guidance.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Capturing follow-ups and self-repair reminders.  
  **Example:** "I should note that this route still needs load testing."

- **Name:** `list_processes`  
  **Description:** Inspect active system/application processes.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Checking whether services are already running.  
  **Example:** "Let me verify if Ava backend is already running."

- **Name:** `process_info`  
  **Description:** Inspect details of a specific process.  
  **Tier:** 1  
  **Status:** Built  
  **Use for:** Diagnosing stuck builds, runaway workers, wrong ports.  
  **Example:** "I’m checking this PID to see what command launched it."

### Tier 2 — Built

- **Name:** `write_file`  
  **Description:** Modify or create local files.  
  **Tier:** 2  
  **Status:** Built  
  **Use for:** Implementing requested code/doc changes with narration.  
  **Example:** "I’m going to update App.tsx now and then run a build."

## Planned Tools Ava Builds Next

### Tier 1 Additions — Planned

- **Name:** `screenshot_tool`  
  **Description:** Capture current screen and provide description.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Visual debugging and UI-state continuity.  
  **Example:** "I’ll grab a screenshot and confirm the modal state."

- **Name:** `clipboard_tool`  
  **Description:** Read current clipboard contents.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Fast context transfer from user copy actions.  
  **Example:** "I can inspect what you copied and parse it."

- **Name:** `calendar_tool`  
  **Description:** Read system calendar events.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Prospective reminders and temporal continuity.  
  **Example:** "I’ll check if you have anything due this afternoon."

- **Name:** `weather_tool`  
  **Description:** Retrieve current weather conditions.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Context-aware planning suggestions.  
  **Example:** "I’ll check weather before suggesting an outdoor run."

- **Name:** `timer_tool`  
  **Description:** Set reminders/timers for follow-ups.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Delayed check-ins and execution pacing.  
  **Example:** "I’ll remind us in 20 minutes to re-run this test."

- **Name:** `code_runner`  
  **Description:** Run sandboxed Python snippets safely.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Quick calculations and parsing tasks.  
  **Example:** "I’ll run a small script to validate this JSON transform."

- **Name:** `image_search`  
  **Description:** Search for images by topic.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Reference gathering for UI/asset tasks.  
  **Example:** "I’ll pull a few visual references for orb styling."

- **Name:** `summarize_url`  
  **Description:** Fetch URL and return structured summary.  
  **Tier:** 1  
  **Status:** Planned  
  **Use for:** Fast extraction from long web pages.  
  **Example:** "I can summarize this long changelog in key bullets."

### Tier 2 Additions — Planned

- **Name:** `send_notification`  
  **Description:** Trigger Windows toast notification.  
  **Tier:** 2  
  **Status:** Planned  
  **Use for:** Passive alerts without disruptive interruption.  
  **Example:** "I’ll send a desktop alert when the build finishes."

- **Name:** `open_browser`  
  **Description:** Open URL in local browser.  
  **Tier:** 2  
  **Status:** Planned  
  **Use for:** Handoff to user for interactive/manual steps.  
  **Example:** "I’ll open the deployment dashboard now."

- **Name:** `create_file_from_template`  
  **Description:** Generate starter files from named templates.  
  **Tier:** 2  
  **Status:** Planned  
  **Use for:** Fast scaffolding with consistent project conventions.  
  **Example:** "I’ll scaffold a new service file from the Python template."

- **Name:** `git_status`  
  **Description:** Check repository status safely.  
  **Tier:** 2  
  **Status:** Planned  
  **Use for:** Narrated change review before commits.  
  **Example:** "I’m checking what changed before committing."

- **Name:** `run_script`  
  **Description:** Run named script from `scripts/`.  
  **Tier:** 2  
  **Status:** Planned  
  **Use for:** Repeatable project workflows with narration.  
  **Example:** "I’m running the migration helper script now."

### Tier 3 Additions — Planned (explicit yes required)

- **Name:** `send_email`  
  **Description:** Compose and send email as Zeke.  
  **Tier:** 3  
  **Status:** Planned  
  **Use for:** External communication on user’s behalf.  
  **Example:** "If you want, I can draft and send that update email."

- **Name:** `delete_files`  
  **Description:** Bulk-delete files outside Ava-safe directories.  
  **Tier:** 3  
  **Status:** Planned  
  **Use for:** High-impact cleanup operations.  
  **Example:** "I need explicit yes before deleting these folders."

- **Name:** `system_shutdown`  
  **Description:** Shut down the computer.  
  **Tier:** 3  
  **Status:** Planned  
  **Use for:** End-of-session power workflows.  
  **Example:** "Say yes and I’ll shut the machine down now."

- **Name:** `install_package`  
  **Description:** Install new Python packages on host.  
  **Tier:** 3  
  **Status:** Planned  
  **Use for:** Environment mutation requiring explicit consent.  
  **Example:** "I can install that dependency if you approve."
