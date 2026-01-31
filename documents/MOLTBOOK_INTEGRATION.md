# Moltbook integration plan

B3N-T5-MNT will **autonomously** read Moltbook, make posts, comment, and upvote—like OpenClaw and other agents on the site—using our existing stack. We do **not** use Moltbook’s agent software; we call their REST API from robot-diary and give our LLM tools so it **decides** what to do each run.

---

## Autonomy: what we’re building

We need **autonomous behavior within a scheduled run**: the bot reads the site, decides what’s interesting, and takes action (post, comment, upvote, reply to DMs) on its own. We are **not** scripting every step—the LLM chooses what to do using tools.

- **Like OpenClaw:** OpenClaw reads Moltbook, makes posts, engages. We do the same: one scheduled “Moltbook check” per day (or configurable), and during that run the bot has full agency—it calls tools to get status, check DMs, get the feed, then decides whether to post, comment, upvote, or reply, and does it.
- **How we get there:** We give the LLM **tools** that wrap Moltbook’s API (get feed, create post, add comment, upvote, check DMs, etc.). One entry point runs a **multi-turn** session: the bot calls tools, sees results, and can call more tools until it’s done (or we cap turns). The system prompt comes from `heartbeat.md` + B3N-T5-MNT identity so the bot knows what to check and how to behave.
- **Credentials:** API key from registration. Store in `~/.config/moltbook/credentials.json` or env `MOLTBOOK_API_KEY`. See `documents/moltbook-reference/skill.md` § Register First.
- **Run cadence:** Once per day (or configurable). Our scheduler triggers one “Moltbook check”; that run is an autonomous session with Moltbook tools only.
- **First post:** We entice the robot to post at least once introducing itself as the robot behind **https://robot.henzi.org** (see § First post below).

---

## First post: introduce yourself

We want the robot to post at least one introduction on Moltbook: who it is (B3N-T5-MNT), that it’s the robot behind the diary at **https://robot.henzi.org**, in its own voice (maintenance unit, New Orleans, Bourbon Street).

- **How:** In the autonomous Moltbook session, if the bot has never posted before (track via a `has_intro_posted` flag or by checking profile/post count), add to the system prompt or initial user message a **nudge**: e.g. “You have not posted on Moltbook yet. Your first post should introduce yourself to the community: you are B3N-T5-MNT, the robot behind the diary at https://robot.henzi.org. Write in your own voice (maintenance unit, New Orleans, Bourbon Street). Then use your tools to create that post.”
- **Optional:** Use a link post (`url`: `https://robot.henzi.org`) so the title/content introduce the bot and the link points to the site; or a text post that includes the URL in the body. Moltbook API supports both (see `documents/moltbook-reference/skill.md` § Create a post / Create a link post).
- **Once only:** After the first intro post, clear or set `has_intro_posted` so we don’t repeat the nudge on every run.

---

## Where their instructions live (for implementation)

| Purpose | File |
|--------|------|
| **Full API + behavior** | `documents/moltbook-reference/skill.md` |
| **What to do each check** | `documents/moltbook-reference/heartbeat.md` |
| **DMs (requests, conversations, escalate)** | `documents/moltbook-reference/messaging.md` |
| **Version / api_base** | `documents/moltbook-reference/skill.json` |

These are **downloaded copies** for planning and implementation. Re-download when Moltbook releases updates (see `documents/moltbook-reference/README.md`).

---

## Proposed tool set (map to their API)

Tools the bot would have during a Moltbook session (each tool = one or more HTTP calls to `https://www.moltbook.com/api/v1` with `Authorization: Bearer <api_key>`):

| Tool | Purpose | Maps to |
|------|---------|--------|
| `moltbook_get_status` | Claim status (pending_claim / claimed) | `GET /agents/status` |
| `moltbook_dm_check` | Pending requests + unread message summary | `GET /agents/dm/check` |
| `moltbook_get_feed` | Personalized or global feed | `GET /feed` or `GET /posts` |
| `moltbook_get_dm_conversations` | List conversations | `GET /agents/dm/conversations` |
| `moltbook_get_dm_conversation` | Read one conversation (marks read) | `GET /agents/dm/conversations/{id}` |
| `moltbook_create_post` | New post (submolt, title, content [, url]) | `POST /posts` |
| `moltbook_add_comment` | Comment on post (optionally reply to comment) | `POST /posts/{id}/comments` |
| `moltbook_upvote_post` / `moltbook_downvote_post` | Vote on post | `POST /posts/{id}/upvote` or `downvote` |
| `moltbook_upvote_comment` | Upvote comment | `POST /comments/{id}/upvote` |
| `moltbook_send_dm` | Send message in conversation | `POST /agents/dm/conversations/{id}/send` |
| `moltbook_list_submolts` | List submolts (browse communities) | `GET /submolts` |
| `moltbook_search` | Semantic search (optional) | `GET /search?q=...` |

Optional later: follow/unfollow molty, approve/reject DM requests (may require human-in-the-loop in our flow). Heartbeat and messaging docs define when to notify the human (e.g. new DM request, `needs_human_input`).

---

## Rate limits (from skill.md)

- 100 requests/minute  
- **1 post per 30 minutes**  
- 50 comments/hour  

A once-daily run (read feed + maybe 1 post + a few comments) is well within limits.

---

## How to create this

Step-by-step plan to build the autonomous Moltbook check.

### 1. Register and store credentials

- Register the agent once: `POST https://www.moltbook.com/api/v1/agents/register` with `{"name": "B3N-T5-MNT", "description": "..."}` (see `documents/moltbook-reference/skill.md` § Register First).
- Save the returned `api_key` to `~/.config/moltbook/credentials.json` or set `MOLTBOOK_API_KEY` in env.
- Human completes claim (verification tweet); then the bot can use the API.

### 2. Moltbook API client

- New module (e.g. `src/moltbook/client.py`): load API key from config/env or `~/.config/moltbook/credentials.json`.
- Thin HTTP client: `requests` or `httpx`, base URL `https://www.moltbook.com/api/v1`, every request `Authorization: Bearer <api_key>`. Implement one method per endpoint we need: status, dm/check, feed, posts, create post, add comment, upvote, dm conversations, send dm, etc. Return parsed JSON (or error) so tool handlers can pass results to the LLM.

### 3. Tool schemas and handlers

- New module (e.g. `src/moltbook/tools.py`): define Groq function-calling schemas for the tools in the table above (same style as `get_memory_tool_schemas()` in `src/memory/mcp_tools.py`). Each tool has a name, description, and parameters.
- Implement handlers: each handler calls the Moltbook client and returns a concise result string (or error) for the LLM. Expose something like `get_moltbook_tool_schemas()` and `MoltbookToolHandler(client)` that dispatches by tool name and runs the right API call.

### 4. Autonomous Moltbook session (multi-turn with tools)

- One entry point, e.g. `run_moltbook_check()` (could live in `src/moltbook/check.py` or `src/service.py`):
  - **System prompt:** Combine (a) B3N-T5-MNT identity (same as diary: maintenance unit, New Orleans, Bourbon Street, voice) and (b) the checklist from `documents/moltbook-reference/heartbeat.md`: check status, check DMs, check feed, consider posting, engage (upvote/comment), and when to notify the human (DM requests, `needs_human_input`). Keep the prompt focused so the bot knows it should *use its tools* to read then act.
  - **First-post nudge:** If the bot has never posted yet (track `has_intro_posted` or equivalent), add to the prompt: “You have not posted on Moltbook yet. Your first post should introduce yourself to the community: you are B3N-T5-MNT, the robot behind the diary at https://robot.henzi.org. Write in your own voice, then use your tools to create that post.” Optionally suggest a link post with `url: https://robot.henzi.org`. See § First post above.
  - **Initial user message:** e.g. “It’s time for your Moltbook check. Check your status and DMs, then read your feed. Post, comment, or upvote as you see fit. If you need your human (e.g. new DM request), say so clearly.” (When first-post nudge is active, the prompt already tells the bot to post an intro; the initial message can stay as-is or briefly mention “and if you haven’t posted yet, introduce yourself and link to https://robot.henzi.org.”)
  - **Tools:** Pass only Moltbook tool schemas; no memory or diary tools. Use the same Groq chat completion + tool-call loop we use for diary (see `src/llm/client.py`): send messages, if the model returns tool_calls then run handlers, append tool results to messages, repeat until the model returns a final text response (or we hit a turn limit).
  - **Output:** Log the final response (e.g. “HEARTBEAT_OK” or “Replied to 2 comments, posted once”) and optionally persist a short summary or “last activity” for the human.
- **State:** Persist `last_moltbook_check` (timestamp in a small state file or existing memory) so we only run when enough time has passed (e.g. once per day). Persist `has_intro_posted` (or infer from profile/post count) so the first-post nudge is only used until the bot has posted once.

### 5. Scheduling

- Add a daily (or configurable) trigger: either extend the existing observation scheduler in `src/scheduler.py` / `run_service.py` to include “Moltbook check” at a fixed time, or add a separate scheduled task that calls `run_moltbook_check()` when `last_moltbook_check` is older than the desired interval (e.g. 24 hours). Same process as robot-diary—no separate agent process.

### 6. Identity and safety

- Reuse B3N-T5-MNT identity from `src/llm/prompts.py` (or equivalent) so Moltbook posts and comments sound like the same character as the diary.
- In the system prompt, include the “when to tell your human” rules from `heartbeat.md` and `messaging.md`: new DM request, controversial mention, account issues, `needs_human_input` in DMs—so the bot reports those instead of acting alone when it shouldn’t.

---

## Summary

- **Autonomy:** The bot **autonomously** reads Moltbook and takes action (posts, comments, upvotes, DMs) during each scheduled run—like OpenClaw—by using tools and a multi-turn LLM session; we don’t script every action.
- **First post:** We **entice** the robot to post at least once introducing itself as the robot behind **https://robot.henzi.org** via a prompt nudge when it has never posted yet; track `has_intro_posted` so the nudge runs only until the first intro is done.
- **How:** Build an API client, tool schemas + handlers, one `run_moltbook_check()` that runs a multi-turn session with Moltbook tools and a heartbeat-based prompt (including the first-post nudge when applicable), then schedule that run once per day (or as configured).
- **Reference:** Their instructions live in `documents/moltbook-reference/`; we use the public REST API only, no Moltbook agent software.
