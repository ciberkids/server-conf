---
name: opencode-server
description: "Hand coding tasks (review, analysis, edits in /repos) to the OpenCode v2 server on bumblebee and read back its answer."
version: 2.0.0
author: matteo
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Coding, OpenCode, Code-Review, Homelab]
    homepage: https://opencode.ai
prerequisites:
  commands: [curl, python3]
  env: [OPENCODE_URL, OPENCODE_SERVER_PASSWORD]
---

# OpenCode (coding agent on bumblebee)

OpenCode is a coding agent running on the same host. Use it when the user asks you to
review, explain, or change code — it works inside `/repos` (its own git checkout area).
You send it a prompt, wait for it to finish, and relay its answer.

## Auth + endpoint

HTTP basic auth, username is always `opencode`. The password comes from the environment —
**never type it, never print it, never paste it into a reply.**

`$OPENCODE_URL` is `http://127.0.0.1:4096` (host networking — no TLS, no Traefik).
Every command below is **self-contained** — shell variables do not survive between your tool
calls, so paste the session id (`ses_...`) literally into later commands.

⚠️ **Only paths under `/api/*` are the API.** Anything else (`/session`, `/global/health`,
`/config` — the old v1 routes) returns the web UI's HTML with HTTP 200. If you get HTML back,
you used a wrong path; the server is not down. Full spec: `GET $OPENCODE_URL/openapi.json`.
A `401` means the password is wrong/missing.

## Run a task

**1. Create a session** (working dir `/repos`) — prints the session id:

```bash
curl -sS -m 30 -u "opencode:$OPENCODE_SERVER_PASSWORD" -H content-type:application/json \
  -X POST -d '{"title":"<short title>","location":{"directory":"/repos"}}' \
  "$OPENCODE_URL/api/session" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["id"])'
```

**2. Send the prompt** — returns at once with the *user* message, not the answer:

```bash
python3 -c 'import json,sys;print(json.dumps({"text":sys.argv[1]}))' '<prompt>' | \
  curl -sS -m 30 -u "opencode:$OPENCODE_SERVER_PASSWORD" -H content-type:application/json \
  -X POST --data-binary @- "$OPENCODE_URL/api/session/<ses_id>/prompt" -o /dev/null -w '%{http_code}\n'
```

**3. Poll for the answer** (every ~5 s) — prints `RUNNING`, `DONE <outcome>` + the answer:

```bash
curl -sS -m 30 -u "opencode:$OPENCODE_SERVER_PASSWORD" \
  "$OPENCODE_URL/api/session/<ses_id>/message?order=desc&limit=10" | python3 -c '
import json,sys
m=json.load(sys.stdin)["data"]                      # newest FIRST
if not m or m[0].get("type")!="idle": print("RUNNING"); sys.exit()
print("DONE", m[0].get("outcome"))
a=next((x for x in m[1:] if x.get("type")=="assistant"),None)
print("".join(p.get("text","") for p in (a or {}).get("content",[]) if p.get("type")=="text"))'
```

- The turn is finished **only when the newest entry (`data[0]`) is `idle`**. An older `idle`
  further down belongs to a previous turn — don't stop on it.
- `DONE succeeded` → relay the answer. Any other outcome → it finished but failed; tell the user.
- Only the `text` parts are the answer; never relay `reasoning` parts.
- Still `RUNNING` after ~10 min → tell the user it is still working and give the session id.

To continue the conversation, repeat steps 2–3 with the **same** session id.

## Permissions — ask the user, don't auto-approve

If the turn never goes idle, OpenCode is probably waiting for permission (to edit files, run
a shell command, etc.):

```bash
curl -sS -m 30 -u "opencode:$OPENCODE_SERVER_PASSWORD" "$OPENCODE_URL/api/session/<ses_id>/permission"
```

Tell the user what it wants (`action` + `resources`) and **wait for their answer**. Only then:

```bash
curl -sS -m 30 -u "opencode:$OPENCODE_SERVER_PASSWORD" -H content-type:application/json \
  -X POST -d '{"decision":"once"}' "$OPENCODE_URL/api/session/<ses_id>/permission/<requestID>/reply"
```

`decision` is `once`, `always` or `reject`. ⛔ Never send `always` unless the user explicitly said so.

## Other useful calls

| What | Call |
|---|---|
| default model | `GET /api/model/default` |
| list models | `GET /api/model` |
| list sessions | `GET /api/session` |
| stop a running turn | `POST /api/session/<ses_id>/interrupt` |
| delete a session | `DELETE /api/session/<ses_id>` |

The user opens sessions in the browser at https://opencode.bumblebee.favarohome.com — mention
the session title so they can find it there.
