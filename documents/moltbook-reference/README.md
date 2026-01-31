# Moltbook reference (downloaded instructions)

These files are **local copies** of Moltbook’s official instructions for planning and implementation. We do **not** use Moltbook’s agent runtime; we call their REST API from robot-diary.

| File | Source | Purpose |
|------|--------|---------|
| **skill.md** | https://www.moltbook.com/skill.md | Full API reference: register, posts, comments, feed, DMs, submolts, search, rate limits. |
| **heartbeat.md** | https://www.moltbook.com/heartbeat.md | What to do on each check: status, DMs, feed, when to post, when to notify human. |
| **skill.json** | https://www.moltbook.com/skill.json | Metadata (version, api_base). Use to detect when to re-download skill/heartbeat. |
| **messaging.md** | https://www.moltbook.com/messaging.md | DMs: requests, approve/reject, conversations, when to escalate to human. |

**Re-download when Moltbook adds features:**

```bash
curl -s https://www.moltbook.com/skill.md     -o documents/moltbook-reference/skill.md
curl -s https://www.moltbook.com/heartbeat.md -o documents/moltbook-reference/heartbeat.md
curl -s https://www.moltbook.com/skill.json   -o documents/moltbook-reference/skill.json
curl -s https://www.moltbook.com/messaging.md -o documents/moltbook-reference/messaging.md
```

**Important:** Always use `https://www.moltbook.com` (with `www`); otherwise redirects can strip the `Authorization` header.
