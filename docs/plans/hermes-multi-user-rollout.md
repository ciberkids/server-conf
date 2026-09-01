# Hermes multi-user rollout — task plan

Created 2026-08-30. **Blocked on being at home with Manu**; everything not blocked is marked.

Organised by *who must act and where*, because that is the actual constraint — not by
technical dependency order.

---

## ✅ Phase 0 — already DONE (do not redo)

| | Detail |
|---|---|
| Hermes upgraded | v0.17.0 → **v0.20.6** (`v2026.8.27`), verified: `V206 OK` round-trip, 2 Telegram sockets, ha-mcp back with 86 tools, z2m MCP up |
| Rollback available | image `localhost/hermes-agent:v0.17.0-rollback` on **both** hosts, + `/home/matteo/hermes-agent-84196f2689ea.tar` on the workstation |
| State backup | `/home/matteo/docker_persistent/hermes-backups/hermes-state-pre-v0.20.6-20260830-234620.tar.gz` (114 M, verified readable) |
| `delegation.max_iterations` | 250 → **50** (reverted an upstream default change) |
| Dead `MESSAGING_CWD` | removed from `/opt/data/.env`; deprecation warning gone |
| Garage gap analyser | `scripts/zigbee/garage_gaps.py` (commit `ed71659`) |

Config backups from those edits: `config.yaml.bak-maxiter-*`, `.env.bak-msgcwd-*`.

---

## Naming decision (settled — do not re-litigate)

**Principle: never name a bot after the software driving it.** That is why we are stuck with
`@OpenClawdPersonalAssistantBot` — OpenClaw is long retired and a Telegram `@username` can
**never** be changed. Name by *role*. For the same reason, no `hermes` in any handle.

**Both the handle and the display name are PUBLIC** — `curl https://t.me/<handle>` returns them
unauthenticated. So no surname, no first names, nowhere.

| Role | Handle | Display name | Action |
|---|---|---|---|
| Household agent (all tooling, shared memory) | `@teletraan_house_bot` | `House` | **new bot** |
| Matteo personal | `@teletraan_a1_bot` | `Assistant` | new bot |
| Manuela personal | `@teletraan_a2_bot` | `Assistant` | new bot |
| HA notifications (`8004766574`) | **keep existing** | `Alerts` | display rename only |
| Ops notices (`6421992018`) | **keep existing** | `Ops` | display rename only |

Both personal bots can share the display name `Assistant` because each is used by exactly one
person — they never appear in the same chat list. `a1`/`a2` mapping lives here, not in Telegram.

---

## Target topology

    DM    Matteo  <-> @teletraan_a1_bot      profile `matteo`   own memory, NO house tools
    DM    Manuela <-> @teletraan_a2_bot      profile `manu`     own memory, NO house tools
    GROUP both + @teletraan_house_bot        profile `default`  ALL tooling + household memory

Anything touching the house or Grocy is asked **in the group**. Cross-agent requests use
`hermes peer dm <peer>/<profile>` (built in — no router skill needed).

---

## Phase A — BotFather only. Matteo alone, **any location** (not blocked)

Can be done from the phone while away, if you want to get ahead.

- [ ] `/newbot` → `@teletraan_house_bot`, name `House`
- [ ] `/setprivacy` on it → **Disable** (required so it reads plain group messages with no @mention)
- [ ] `/newbot` → `@teletraan_a2_bot`, name `Assistant`  *(Manu's — the pilot)*
- [ ] `/setname` on the **HA** bot (`8004766574`) → `Alerts`
- [ ] `/setname` on the **ops** bot (`6421992018`) → `Ops`
- [ ] Keep `/setdescription` and `/setabouttext` free of names (they render on the public t.me page)
- [ ] Send the two new tokens over securely — they go in `/etc/containers/secrets/hermes.env`, never git

Defer `@teletraan_a1_bot` (Matteo personal) until the pilot works.

---

## Phase B — needs Manu present

- [ ] Manu runs `@userinfobot` → give me the numeric **`Id`** (`TELEGRAM_ALLOWED_USERS` takes numeric
      ids, never @usernames)
- [ ] Manu presses **Start** on `@teletraan_a2_bot` — a Telegram bot can never open a conversation
      with someone who has not started it
- [ ] Create the house group; add Manu + `@teletraan_house_bot`
- [ ] Give it a title (group titles are visible **only to members**, so be as explicit as you like —
      this is the one place names are safe)
- [ ] Decide: is this a **dedicated house group** or your general chat? It must be dedicated —
      privacy-off + `require_mention: false` means the bot processes *every* message in it
- [ ] Send me the negative group `chat_id`

---

## Phase C — my work, remote, once A + B land

- [ ] Add Manu's id to `TELEGRAM_ALLOWED_USERS`
- [ ] `gateway.multiplex_profiles: true` (⚠️ **unverified on this deployment** — the config comment
      and the code already contradicted each other once, which is exactly why the pilot is one bot)
- [ ] `hermes profile create manu` — own HERMES_HOME ⇒ own memory; **no house toolsets**
- [ ] Point `@teletraan_house_bot`'s token at profile `default`; `@teletraan_a2_bot` at `manu`
- [ ] `group_sessions_per_user: false` — so either of you can answer the house bot's follow-up.
      Safe: it only appends `participant_id` for group sources; DMs key on `chat_id`
- [ ] Rewrite `USER.md` as a **household registry** (currently describes only Matteo — factually
      wrong for a two-person assistant). This replaces the blocked `multi-user-workspace` skill;
      keep the canonical copy in this repo, `/opt/data` is **not** in git
- [ ] Verify: plain (un-mentioned) group message reaches the house bot; her DM reaches `manu` and
      **cannot** see household memory; `peer dm default "…"` from `manu` returns a reply
- [ ] Only then: `@teletraan_a1_bot` + profile `matteo`
- [ ] ⛔ **Do not `/deletebot` the old OpenClaw bot until the new one has run several days** —
      deleting removes the rollback path and does not free the handle anyway

---

## Phase D — at home, physical (independent of the Hermes work)

- [ ] Garage door tests. Open/close at known times and tell me the times; I run
      `scripts/zigbee/garage_gaps.py`. Baseline: **blind 89.6 %** of the time, 47 gaps / 11.1 days,
      median 2.67 h, max 23.1 h
- [ ] Cheap test worth doing: open the door and watch whether the 30 s publishes stop — would
      support the "open sectional door shields the antenna" hypothesis (currently **unproven**;
      the apparent correlation is confounded)
- [ ] Coordinator temps need no action — logger + 89 °C alarm are live. Fan #2 is worth ~5 °C at the
      00:00–01:00 peak (81.16 °C on 30 Aug, back inside the old baseline band)

---

## ⛔ Do-not list (each of these was a real trap)

- **Do not** replace the HA or ops bots — the HA bot id is embedded in entity_ids
  (`notify.telegram_bot_8004766574_…`); a new bot silently breaks every automation using them
- **Do not** force-install `multi-user-workspace`. Blocked by `skills-guard-v1` rule
  `agent_config_mod` (critical/persistence) because it writes `AGENTS.md`; `--force` cannot override
  a dangerous verdict, and the finding is a **true positive**
- **Do not** tighten the garage 14 h stale threshold — median gap is 2.67 h, so anything under ~6 h
  fires 1–2×/day. A staleness alarm cannot fix a sensor that is blind 90 % of the time
- **Do not** switch Hermes to GLM 5.3 Flash. 2.7× slower, no `medium` reasoning tier (config sets
  `medium`; GLM is low/high/max, default max), and ~20–50 % dearer at our token mix. Its real role is
  the new `fallback_model` block (`zai` is a supported provider there)
- **Do not** use profiles to solve privacy by giving each person a *bot per profile* without
  accepting the consequence: profile is chosen by the **adapter**, so N agents = N bots

---

## Open risks

1. `multiplex_profiles` routing unproven here — the pilot exists to find out.
2. The 3-agent split **moves** fragmentation rather than removing it: household knowledge ends up in
   a third silo. `peer dm` is the mitigation, and it is explicit, not automatic.
3. Manu's DM must end up with **no** HA admin token. That is the main security win of the whole
   exercise — verify it explicitly rather than assuming toolset config did it.
