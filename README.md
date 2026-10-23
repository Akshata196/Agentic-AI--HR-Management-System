# AtliQ HR Assist — Agentic HR Workflow (Upgrade in Progress)

An MCP-based HR assistant designed for interactive use with Claude Desktop. The current implementation exposes employee, leave, meeting, ticket and email operations. This upgrade adds safer error reporting, consistent demo data, stdio-safe tool logging, initial manager tests and an evaluation dataset.

> **Status:** The current upgraded branch is an incremental foundation. SQLite/SQLAlchemy persistence, manager-approval leave workflows, RAG policy search, complete RBAC, full audit storage and the Claude-agent golden-task runner are planned next phases and should not be claimed as implemented yet.

## Architecture today

```text
Claude Desktop
    | MCP over stdio
    v
server.py (FastMCP tools and onboarding prompt)
    |-- hrms/employee_manager.py
    |-- hrms/leave_manager.py
    |-- hrms/meeting_manager.py
    |-- hrms/ticket_manager.py
    |-- emails.py (SMTP adapter)
    |-- utils.py (demo seed data)
    `-- observability.py (tool outcome and latency logs to stderr)
```

## Setup

Requires Python 3.13+ and `uv`.

1. Create an isolated environment and install dependencies:

   ```bash
   uv sync
   ```

2. Copy `.env.example` to `.env` and fill in the email account and Gmail app password locally. Never commit `.env`.
3. Run tests:

   ```bash
   uv run pytest -q
   ```

4. Run the MCP development inspector:

   ```bash
   uv run mcp dev server.py
   ```

5. For Claude Desktop, configure the local MCP server to launch `uv run --directory /absolute/path/to/atliq-hr-assist python server.py` using the `stdio` transport. Restart Claude Desktop after changing its MCP configuration.

## Security notes

- Email sending is restricted to `HR_ALLOWED_EMAIL_DOMAIN` (defaults to `atliq.com`). Adjust only for a controlled test environment.
- SMTP exceptions are propagated instead of being swallowed; logs avoid email bodies, passwords and argument values.
- `.env`, database files and evaluation outputs are ignored by Git.
- This is not production-ready RBAC. The MCP server still needs an authenticated identity and role-aware authorization before exposing employee/manager/HR privileges in a shared environment.
- Demo data is currently in memory. SQLite persistence is the next planned phase.

## Current tests and evaluation assets

- `tests/test_hrms_managers.py`: initial unit tests for employee, leave, meeting and ticket logic.
- `evaluation/dataset.json`: initial golden-task specification. It is a dataset only; a runner that evaluates actual Claude tool-call traces is still to be implemented.
- `evaluation/metrics.py`: summarizes JSONL results containing `success` and optional `latency_ms` fields.

## Roadmap

1. Complete manager fixes and tests.
2. Move records to SQLite/SQLAlchemy with migrations and idempotency.
3. Add pending leave requests, manager approval/rejection and workflow state.
4. Add HR policy RAG and MCP resources.
5. Add identity-aware RBAC, approval gates and persistent audit events.
6. Add golden-task execution, tool-call trace scoring and regression reports.
7. Add Docker packaging, architecture diagram and demo recording.
