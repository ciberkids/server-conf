---
name: tautulli
description: "Query Tautulli for Plex activity, watch history, library stats and transcode details on Optimus Prime."
version: 1.0.0
author: matteo
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Media, Plex, Tautulli, Homelab, Monitoring]
    homepage: https://tautulli.com
prerequisites:
  commands: [curl, python3]
  env: [TAUTULLI_URL, TAUTULLI_API_KEY]
---

# Tautulli (Plex monitoring)

Read-only access to the Tautulli instance that watches the Plex server on Optimus Prime.
Answers "who is watching what", "what did we watch last month", "is anything transcoding".

## Endpoint

Everything is one GET against a single endpoint. The key comes from the environment —
**never type it, never print it, never paste it into a reply.**

```bash
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=<COMMAND>"
```

`$TAUTULLI_URL` is `http://192.168.1.10:8181` (LAN only — no auth needed beyond the key).
Every response is `{"response": {"result": "success"|"error", "message": ..., "data": ...}}`.
**Always check `.response.result` before trusting `.data`** — Tautulli returns HTTP 200 on
errors too, so a bad command looks like a success at the transport layer.

## ⛔ Allowed commands — read-only ONLY

This key is a **full-admin** key (Tautulli has no read-only scope). Restrict yourself to
the list below. Do **not** call anything that writes, deletes, terminates or restarts,
even if the user asks casually — say what you would run and let them do it in the UI.

| Command | Returns |
|---|---|
| `get_activity` | Current streams: who, what, player, transcode decision |
| `get_history` | Watch history (`user`, `length`, `start`, `search` params) |
| `get_home_stats` | Top movies / shows / users / platforms |
| `get_libraries` | Library sections with counts |
| `get_users` | Plex users known to Tautulli |
| `get_recently_added` | Newest items (`count`, `section_id`) |
| `get_metadata` | Item details (`rating_key`) |
| `get_stream_data` | Transcode detail for one session (`session_key`) |
| `get_plays_by_date` | Play counts per day (`time_range`) |
| `get_plays_per_month` | Play counts per month (`y_axis`, `time_range`) |
| `get_server_info` | Plex server identity/version |

**Never call:** `restart`, `backup_db`, `backup_config`, `terminate_session`,
`delete_*` (library, user, history, cache, image_cache, export, lookup_info,
temp_sessions, media_info_cache), `edit_library`, `edit_user`, `import_database`,
`update`, `refresh_libraries_list`, `refresh_users_list`, `notify`, `register_device`,
`set_mobile_device_config`, `sql`.
(`api_sql` is disabled server-side, so `sql` fails anyway — treat that as a backstop,
not permission to try.)

## Recipes

### Who is watching right now

```bash
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=get_activity" | python3 -c '
import json,sys
d=json.load(sys.stdin)["response"]
if d["result"]!="success": sys.exit(f"tautulli error: {d.get(\"message\")}")
d=d["data"]
print(f"{d[\"stream_count\"]} stream(s)")
for s in d.get("sessions",[]):
    print(f"  {s[\"friendly_name\"]}: {s[\"full_title\"]} "
          f"[{s[\"transcode_decision\"]}] on {s[\"player\"]} ({s[\"progress_percent\"]}%)")
'
```

### Is anything transcoding, and is it using the GPU

Useful because the Grafana `AMD GPU` panel reads ~0 during a hardware transcode
(the VCN video engine bursts far faster than the 30 s Prometheus scrape — see
`docs/homelab-fix-list.md`). Tautulli is the *semantic* answer that graph cannot give.

```bash
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=get_activity" | python3 -c '
import json,sys
for s in json.load(sys.stdin)["response"]["data"].get("sessions",[]):
    hw = "GPU (vaapi)" if s.get("transcode_hw_full_pipeline")=="1" else "CPU"
    print(f"{s[\"full_title\"]}: {s[\"transcode_decision\"]} via {hw}, "
          f"speed={s.get(\"transcode_speed\")}x throttled={s.get(\"transcode_throttled\")}")
'
```

`transcode_speed` well above 1.0 with `transcode_throttled=1` is normal and healthy —
Plex has raced ahead of the player and paused the encoder.

### Watch history

```bash
# last 10 plays overall
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=get_history&length=10"
# for one user
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=get_history&user=Matteo&length=25"
```

### Library sizes

```bash
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=get_libraries" | python3 -c '
import json,sys
for l in json.load(sys.stdin)["response"]["data"]:
    print(f"{l[\"section_name\"]:28} {l[\"section_type\"]:8} {l[\"count\"]}")
'
```

### Top content this month

```bash
curl -sS -m 15 "$TAUTULLI_URL/api/v2?apikey=$TAUTULLI_API_KEY&cmd=get_home_stats&time_range=30&stats_count=5"
```

## Notes

- **LAN only.** `192.168.1.10:8181` is not reachable from the internet; this works because
  Hermes runs on bumblebee with host networking on the same 192.168.1.0/24.
- The Traefik route `https://tautulli.optimusprime.favarohome.com` also works, but prefer the
  direct IP+port — one less moving part, and it does not depend on cert renewal.
- Libraries are `Movies`, `TV Shows`, `Photos`, `Wedding 2021 Picture`, `Wedding 2021 Videos`.
- Tautulli reports on Plex only. Jellyfin runs on the same box and is **not** covered here.
- If a call returns `result: error` with an invalid-apikey message, the key was rotated in
  Tautulli's Settings → Web Interface — the env var needs updating, do not guess a new one.
