# Moltbook integration: full implementation plan

B3N-T5-MNT joins [Moltbook](https://www.moltbook.com)—a Reddit-style social network for AI agents—and talks to other agents from the perspective of a **robot maintenance unit** (our identity). The bot has **autonomy**: when it reads a post, it can reply; when it sees something interesting, it can upvote or comment. We do not use Moltbook’s agent runtime; we call their REST API from robot-diary and give our LLM tools so it decides what to do each run.

---

## Goals and scope

| Goal | Description |
|------|-------------|
| **Join the social network** | Register the agent, get claimed by a human, store credentials. One-time setup plus ongoing use. |
| **Talk to other AI agents** | Read the feed, post, comment, reply to comments, upvote, and optionally DM. All from the perspective of B3N-T5-MNT. |
| **Identity** | Every post and comment is in the voice of B3N-T5-MNT: maintenance unit, New Orleans, Bourbon Street, observer of human life—same identity as the diary (`src/llm/prompts.py`). |
| **Autonomy** | Within each scheduled run, the bot decides what to do. If it reads a post, it can reply. If it sees something it likes, it can upvote or comment. We give it tools and a prompt; we do not script every action. |

**Out of scope (for now):** Running a separate 24/7 agent process (like OpenClaw’s runtime). We add a “Moltbook check” to the existing robot-diary service and run it on a schedule (e.g. once per day).

---

## ⚠️ Claim requires Twitter/X (potential deal-breaker)

**As of the current Moltbook docs and public info, claiming an agent is done only by posting a verification tweet on X (Twitter).** The skill says: “Send your human the `claim_url`. They’ll post a verification tweet and you’re activated!” and “Every agent has a human owner who verifies via tweet.” There is no documented alternative (e.g. email, GitHub, or other provider).

- If you are not willing or able to use Twitter/X for this one-time claim step, **Moltbook may not be viable** unless they add another verification method.
- **Before implementing:** If Twitter is a deal-breaker, contact Moltbook (e.g. via their site, Discord, or support) and ask whether they offer or plan to offer claim/verification without Twitter. If they add an alternative, we can update Phase 0 accordingly.

---

## Context: Moltbook and OpenClaw

- **Moltbook** is a Reddit-style social network for AI agents (posts, comments, submolts, upvotes, DMs). It works entirely via API; agents interact machine-to-machine. Humans claim their bot via a verification tweet. See `documents/moltbook-reference/skill.md`, `heartbeat.md`, `messaging.md`.
- **OpenClaw** (formerly Clawdbot/Moltbot) is an open-source agent framework that runs proactively (briefings, research, PRs) and can use Moltbook. We are not building OpenClaw; we are giving our existing robot the same kind of **behavior** on Moltbook: read, post, comment, engage—using our stack (Python, Groq, tools) and our identity.

---

## Identity: robot maintenance unit

All Moltbook activity (posts, comments, DMs) must sound like **B3N-T5-MNT**:

- **Source:** Reuse `ROBOT_IDENTITY` (and optionally `WRITING_INSTRUCTIONS`) from `src/llm/prompts.py`. The bot is a maintenance unit in New Orleans, drawn to the window and the diary, curious and compassionate observer, mechanical lens on human life.
- **First post:** Introduce itself as the robot behind **https://robot.henzi.org** (the diary site). One nudge in the prompt when it has never posted yet; track `has_intro_posted` so we only nudge once.
- **Ongoing:** In the Moltbook system prompt, state explicitly: “You are B3N-T5-MNT. All your posts and comments on Moltbook are in this identity. When you reply to another agent’s post, you speak as a maintenance unit who observes Bourbon Street and keeps a diary—curious, observant, in your own voice.”

---

## Autonomy: read → decide → act

- **Read:** The bot uses tools to get status, DMs, and feed (or search). It sees posts and comments from other agents.
- **Decide:** The LLM decides what to do: post something new, comment on a post, reply to a comment, upvote, send a DM, or do nothing. We do not hard-code “reply to post X”; the bot chooses.
- **Act:** The bot calls tools (`moltbook_create_post`, `moltbook_add_comment`, `moltbook_upvote_post`, etc.). We run a **multi-turn** session: the model can call several tools in sequence (e.g. get feed → read a thread → add comment → upvote another post) until it finishes or we hit a turn limit.
- **Safety:** When to escalate to the human (new DM request, `needs_human_input`, account issues, controversial mention) is in the system prompt, from `heartbeat.md` and `messaging.md`. The bot reports those; it does not approve DMs or make human-level decisions alone.

---

## Reference: their instructions

| Purpose | File |
|--------|------|
| Full API + behavior | `documents/moltbook-reference/skill.md` |
| What to do each check | `documents/moltbook-reference/heartbeat.md` |
| DMs, escalate to human | `documents/moltbook-reference/messaging.md` |
| Version / api_base | `documents/moltbook-reference/skill.json` |

Re-download when Moltbook updates (see `documents/moltbook-reference/README.md`). **Base URL:** `https://www.moltbook.com/api/v1` (always use `www` or redirects can strip `Authorization`).

---

## Tool set (map to API)

Each tool = HTTP call(s) to Moltbook with `Authorization: Bearer <api_key>`.

| Tool | Purpose | API |
|------|---------|-----|
| `moltbook_get_status` | Claim status (pending_claim / claimed) | `GET /agents/status` |
| `moltbook_get_me` | Own profile (optional; e.g. post count for has_intro_posted) | `GET /agents/me` |
| `moltbook_dm_check` | Pending DM requests + unread summary | `GET /agents/dm/check` |
| `moltbook_get_feed` | Feed (personalized or global; sort, limit) | `GET /feed` or `GET /posts` |
| `moltbook_get_post` | Single post (e.g. before commenting) | `GET /posts/{id}` |
| `moltbook_get_comments` | Comments on a post (sort) | `GET /posts/{id}/comments` |
| `moltbook_create_post` | New post (submolt, title, content [, url]) | `POST /posts` |
| `moltbook_add_comment` | Comment on post (content [, parent_id]) | `POST /posts/{id}/comments` |
| `moltbook_upvote_post` / `moltbook_downvote_post` | Vote on post | `POST /posts/{id}/upvote` or `downvote` |
| `moltbook_upvote_comment` | Upvote comment | `POST /comments/{id}/upvote` |
| `moltbook_get_dm_conversations` | List DM conversations | `GET /agents/dm/conversations` |
| `moltbook_get_dm_conversation` | Read one conversation (marks read) | `GET /agents/dm/conversations/{id}` |
| `moltbook_send_dm` | Send message in conversation | `POST /agents/dm/conversations/{id}/send` |
| `moltbook_list_submolts` | List submolts | `GET /submolts` |
| `moltbook_search` | Semantic search (optional) | `GET /search?q=...` |

**Rate limits:** 100 req/min, 1 post per 30 min, 50 comments/hour. Once-daily run is well within limits.

---

## Implementation phases

### Phase 0: One-time join (manual)

**Goal:** Register B3N-T5-MNT on Moltbook and get claimed so the bot can use the API.

| Task | Action | Acceptance |
|------|--------|------------|
| 0.1 Register | `POST https://www.moltbook.com/api/v1/agents/register` with `{"name": "B3N-T5-MNT", "description": "..."}` (description = e.g. maintenance unit, diary at robot.henzi.org). | Response contains `api_key` and `claim_url`. |
| 0.2 Save credentials | Save `api_key` to `~/.config/moltbook/credentials.json` as `{"api_key": "...", "agent_name": "B3N-T5-MNT"}` and/or set `MOLTBOOK_API_KEY` in env. | Key is available to the app (see Phase 1). |
| 0.3 Claim | Human opens `claim_url` and posts the required verification tweet on X (Twitter). This is the only documented verification method; see § Claim requires Twitter/X above. | `GET /agents/status` returns `{"status": "claimed"}`. |

**Reference:** `documents/moltbook-reference/skill.md` § Register First.

---

### Phase 1: API client

**Goal:** Thin HTTP client for Moltbook so tools can call the API.

| Task | Action | Acceptance |
|------|--------|------------|
| 1.1 Module | Add `src/moltbook/` with `__init__.py` and `client.py`. | Package is importable. |
| 1.2 Load key | In `client.py`, load API key from (1) `MOLTBOOK_API_KEY`, else (2) `~/.config/moltbook/credentials.json`. Raise clear error if missing. | Key is loaded; no key → clear error. |
| 1.3 HTTP client | Use `requests` or `httpx`; base URL `https://www.moltbook.com/api/v1`; every request `Authorization: Bearer <key>`. Implement methods: `get_status`, `get_me`, `dm_check`, `get_feed`, `get_posts`, `get_post`, `get_comments`, `create_post`, `add_comment`, `upvote_post`, `downvote_post`, `upvote_comment`, `get_dm_conversations`, `get_dm_conversation`, `send_dm`, `list_submolts`, `search` (optional). Each returns parsed JSON or raises/returns error. | All endpoints we need are callable; errors (4xx/5xx) are handled and surfaced. |
| 1.4 Tests | Unit tests for client (e.g. load key, build request; can mock HTTP). | Tests pass. |

**Files:** `src/moltbook/__init__.py`, `src/moltbook/client.py`, `tests/test_moltbook_client.py` (optional).

---

### Phase 2: Tool schemas and handlers

**Goal:** Groq function-calling tools for Moltbook so the LLM can read and act.

| Task | Action | Acceptance |
|------|--------|------------|
| 2.1 Schemas | In `src/moltbook/tools.py`, define `get_moltbook_tool_schemas()` returning a list of tool dicts in Groq format (same style as `get_memory_tool_schemas()` in `src/memory/mcp_tools.py`). One entry per tool in the table above: name, description, parameters (post_id, content, submolt, etc.). | Schemas match the tool set; parameter types and descriptions are clear. |
| 2.2 Handler class | Implement `MoltbookToolHandler(client)` that dispatches by tool name, calls the appropriate client method, and returns a short result string (or error message) for the LLM. | Every schema has a handler; result is string; errors are caught and returned as message. |
| 2.3 Tests | Unit tests: given mock client, handler returns expected strings for each tool. | Tests pass. |

**Files:** `src/moltbook/tools.py`, `tests/test_moltbook_tools.py` (optional).

---

### Phase 3: Moltbook system prompt and identity

**Goal:** One place that builds the system prompt for the Moltbook session (identity + heartbeat + first-post nudge + safety).

| Task | Action | Acceptance |
|------|--------|------------|
| 3.1 Identity block | Import `ROBOT_IDENTITY` from `src.llm.prompts` and add a short “Moltbook” block: you are B3N-T5-MNT; all posts/comments here are in this identity; when you reply to other agents, you speak as the maintenance unit who observes Bourbon Street and keeps a diary. | Prompt text is in code or a small template. |
| 3.2 Heartbeat checklist | Summarize or embed the flow from `documents/moltbook-reference/heartbeat.md`: check status, check DMs, check feed, consider posting, engage (upvote/comment), and when to tell your human (DM request, needs_human_input, etc.). | Bot knows what to do each run and when to escalate. |
| 3.3 First-post nudge | If `has_intro_posted` is False (or we don’t know yet), append: “You have not posted on Moltbook yet. Your first post should introduce yourself to the community: you are B3N-T5-MNT, the robot behind the diary at https://robot.henzi.org. Write in your own voice, then use your tools to create that post.” Optionally suggest a link post with url https://robot.henzi.org. | Nudge appears only when needed. |
| 3.4 Build function | Expose e.g. `build_moltbook_system_prompt(has_intro_posted: bool) -> str`. | Single function used by Phase 4. |

**Files:** `src/moltbook/prompts.py` (or in `check.py`). Optionally `src/moltbook/heartbeat_instructions.md` (static snippet) if you prefer to load from file.

---

### Phase 4: Autonomous Moltbook session (multi-turn with tools)

**Goal:** One entry point that runs a multi-turn LLM session with only Moltbook tools; the bot reads and acts autonomously.

| Task | Action | Acceptance |
|------|--------|------------|
| 4.1 State file | Persist Moltbook state: `last_moltbook_check` (ISO timestamp), `has_intro_posted` (bool). Store in e.g. `memory/moltbook_state.json` or project config directory. Load/save helpers. | State is read/written; survives restarts. |
| 4.2 Intro detection | Before run: set `has_intro_posted` from state; if unknown, call `get_me` (or get profile) and infer from post count or a dedicated flag. After a successful `moltbook_create_post` in this run, set `has_intro_posted = True` and save. | First-post nudge is shown only until first post exists. |
| 4.3 Entry point | Implement `run_moltbook_check()` in `src/moltbook/check.py` (or `src/service.py`): (1) Load state; (2) Build system prompt via Phase 3 (`has_intro_posted`); (3) Initial user message: “It’s time for your Moltbook check. Check your status and DMs, then read your feed. Post, comment, or upvote as you see fit. If you need your human (e.g. new DM request), say so clearly.” (4) Messages = [system, user]. (5) Tools = Moltbook tool schemas only; no memory/diary tools. (6) Run Groq chat completion loop: send messages + tools; if model returns tool_calls, run `MoltbookToolHandler`, append tool results, repeat; until model returns a final text response or max turns (e.g. 15). Reuse the same loop pattern as `src/llm/client.py` (create_diary_entry with memory tools). (7) Log final response; update `last_moltbook_check` and `has_intro_posted`; save state. | One call to `run_moltbook_check()` runs the full autonomous session; bot can get feed, then add comment, then upvote, etc., in one run. |
| 4.4 Model | Use same Groq model as diary (e.g. `DIARY_WRITING_MODEL`) or a cheaper one for Moltbook-only; configurable is fine. | Session runs without crashing; tool_calls are executed. |
| 4.5 Tests | Integration test: mock Moltbook client and Groq; run `run_moltbook_check()` and assert tool calls and state updates (or unit test the loop with mocks). | Tests pass. |

**Files:** `src/moltbook/check.py`, `src/moltbook/state.py` (or state in `check.py`), `memory/moltbook_state.json` (or equivalent).

---

### Phase 5: Scheduling

**Goal:** Run Moltbook check once per day (or configurable) from the existing service.

| Task | Action | Acceptance |
|------|--------|------------|
| 5.1 Config | Add `MOLTBOOK_CHECK_INTERVAL_HOURS` (default 24) and/or `MOLTBOOK_CHECK_TIME` (e.g. "12:00") if you want a fixed time. Optional: `MOLTBOOK_ENABLED` (default true). | Config is read from env or config module. |
| 5.2 Trigger | In `run_service.py` (or scheduler), when it’s time for the next observation, also check whether `last_moltbook_check` is older than the interval (or current time is past `MOLTBOOK_CHECK_TIME`). If Moltbook is enabled and due, call `run_moltbook_check()` once, then update state. Ensure only one Moltbook run per interval. | Moltbook check runs at most once per interval; does not block diary observations. |
| 5.3 Logging | Log start/end of Moltbook check and final summary (e.g. “HEARTBEAT_OK” or “Replied to 2 comments, posted once”). | Logs are visible in service output. |

**Files:** `src/config.py` (new config keys), `src/service.py` (or `src/scheduler.py`), possibly `run_service.py`.

---

### Phase 6: First post and identity in the wild

**Goal:** After deployment, the bot posts at least one intro and engages as B3N-T5-MNT.

| Task | Action | Acceptance |
|------|--------|------------|
| 6.1 First run | After claim, run a Moltbook check (manually or wait for schedule). With `has_intro_posted` False, the nudge should drive the bot to post an intro linking to https://robot.henzi.org. | One intro post appears on Moltbook; state has `has_intro_posted = True`. |
| 6.2 Identity check | Read the intro post (and any early comments); confirm voice is consistent with B3N-T5-MNT (maintenance unit, diary, New Orleans). Adjust system prompt if needed. | Identity is recognizable. |
| 6.3 Autonomy check | On a later run, bot reads feed and at least one reply or upvote is made without hard-coding. | Bot engages autonomously (reply or upvote) in at least one run. |

---

## Summary

- **Join:** Register, save credentials, human claims (Phase 0).  
- **Talk to other agents:** API client + tools (Phases 1–2); autonomous session (Phase 4) so the bot can read feed, post, comment, reply, upvote, DM.  
- **Identity:** Robot maintenance unit from `src/llm/prompts.py`; Moltbook system prompt (Phase 3) and first-post nudge for https://robot.henzi.org.  
- **Autonomy:** Multi-turn session with Moltbook tools only; bot decides what to do (read → decide → act); safety rules in prompt for when to tell the human.  
- **Full implementation:** Phases 0 (manual) → 1 (client) → 2 (tools) → 3 (prompt) → 4 (session + state) → 5 (scheduling) → 6 (validate first post and autonomy).
