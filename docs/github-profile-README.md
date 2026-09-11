# ciberkids

I run a two-server homelab and automate the house it sits in. Most of what I build is
infrastructure nobody is supposed to notice: containers that update themselves, lights that
come on because you walked through a doorway, receipts that file themselves, and a monitoring
stack that tells me when any of it stops being true.

I work in the open because the debugging is the interesting part. Almost everything below
exists because something broke in a way that wasn't in the docs — a container restart loop that
ran out of filesystem path, a presence sensor that latched on for three hours, a notification
system that had never once delivered a notification. The fixes are usually one line. Finding
them was not.

Mostly Linux, podman, systemd, Home Assistant, Zigbee and ESP32. Not much of a web developer.

---

## The homelab

| Project | What it is | Why it exists |
|---|---|---|
| **[server-conf](https://github.com/ciberkids/server-conf)** | The whole homelab as code — 76 podman quadlet units across two hosts, 6 container networks, Traefik routing, Ansible for the workstation, plus 11 docs of architecture notes and incident write-ups. 273 commits since May 2024. | Everything is a `systemd` unit, not a `docker-compose` file. Quadlets mean dependency ordering, `OnFailure=` handlers and `AutoUpdate=registry` come from the init system instead of from a YAML dialect that has to reinvent them. The repo is the source of truth; the servers are downstream of it. |
| **[immich-podman-systemd](https://github.com/ciberkids/immich-podman-systemd)** | Podman quadlet units for running Immich under systemd. | Self-hosted photos without a Docker daemon. Rootless, socket-activated, and restartable by `systemctl` like anything else on the box. |

**Two hosts, deliberately different.** One runs Arch with a 10G SFP+ link, a hardware RAID HBA
and the storage-and-media half of the house. The other runs AlmaLinux with SELinux enforcing and
a GPU, and does all the inference — NVR object detection and a local LLM. Running two distinct
distros is more work and worth it: every SELinux label bug and every `:Z` versus `:z` mistake gets
caught on one host before it can become a habit on both.

## Built for the house

| Project | What it is | Why it exists |
|---|---|---|
| **[water-flow-meter-StampPLC](https://github.com/ciberkids/water-flow-meter-StampPLC)** | Hall-effect water flow meter on an M5Stack StampPLC. | I wanted whole-house water use in the same graphs as electricity. Nothing off the shelf spoke a protocol I already had a broker for. |
| **[cloud-drive-sync](https://github.com/ciberkids/cloud-drive-sync)** | Google Drive syncer. | The alternatives either wanted a subscription or a daemon I couldn't inspect. Also the source of my favourite bug: a 19 MB WebDAV `PROPFIND` response, 138k nested lock properties deep, that starved a Nextcloud instance of logins. |
| **[NodeRedFlows](https://github.com/ciberkids/NodeRedFlows)** | Node-RED flows, mostly Modbus. | Three RS485 gateways and an energy meter that reports demand in watts at one register block and cumulative energy 250 registers away. The flows are the documentation. |
| **[bash-commands](https://github.com/ciberkids/bash-commands)** · **[bash-home](https://github.com/ciberkids/bash-home)** | Self-made shell commands and my dotfiles. | Every homelab grows a private CLI. Mine moves media, prunes empty directories after an `rsync`, and does the things I got tired of typing. |
| **[ObsidianNote](https://github.com/ciberkids/ObsidianNote)** | Git backup of my Obsidian vault. | Notes I would be upset to lose, in a format that will still open in twenty years. |

## Things that broke, and what they turned out to be

The write-ups I'd actually want someone else to find. Each one cost hours and reduces to a
sentence.

| Symptom | What it actually was |
|---|---|
| A container died and came back with `Failed to spawn executor: Device or resource busy`. | Not a busy device — a **too-long path**. `HealthOnFailure=restart` plus podman's `--cgroups=split` appends one nesting level per in-place restart. After ~498 restarts the cgroup path crossed `PATH_MAX` at 4096 bytes. The trigger was an upstream release moving a class into a namespace. |
| A server answered ping and TCP but refused every SSH connection. Looked exactly like dead hardware. | The root filesystem hit 100%. **`sshd` dies while the kernel keeps answering pings**, so the failure impersonates a dead box perfectly. Now I check disk space before I suspect hardware. Proof came from the *other* server's Prometheus, because the sick one couldn't write its own journal. |
| Telegram alerts for failed services: zero complaints for months. | They had **never worked** — 25 failures, 0 deliveries, on both hosts, for different reasons (an SELinux exec denial on one, a non-root `mkdir` on the other). It was masked because the *success* notifier took a different code path and worked fine. An error log that is quiet and a thing that was never exercised are the same observation. |
| Zigbee smart plugs that report their state perfectly but reject every command sent to them. | They **never answer route discovery**. Inbound reports ride the network's concentrator route, so uplink works; downlink has no route at all and silently exhausts its retries. Not a hardware fault, which is what I'd concluded twice. |
| GPU showing 0% utilisation in the middle of a hardware transcode. | **Sampling aliasing**, not a dead sensor: 30-second scrapes against video-engine bursts lasting 1–4 seconds. Only 0.14% of samples caught one. `max_over_time` doesn't rescue it either — you need an exporter that samples fast. |
| A presence-driven light that occasionally never switched off all night. | The night window was a *condition*, not a *trigger*. When everything cleared before the window opened, the off-timer fired outside the window, no branch matched, and **nothing ever re-examined the state**. If a time window gates an action, the window's opening has to be a trigger too. |
| A living-room lamp that refused to come on for someone walking in, seemingly at random. | The **staircase light is inside the lux sensor's field of view** and drives it to 250–320 lx, twelve times the darkness threshold, for 30 seconds — and the cats trip that staircase PIR several times a night. Replaced the whole lux test with `sun.sun` elevation, which no lamp in the house can influence. |

## Fun facts

- The servers are named **Optimus Prime** and **Bumblebee**. The Telegram bots are Teletraan.
  This was not planned and is now load-bearing.
- I sized a sensor debounce by measuring **8 presence dropouts in 25 minutes** while standing
  perfectly still in a hallway. mmWave radar loses people who stop moving; the datasheet
  declines to mention it.
- Two cats set off the motion sensors and turn the lamps on at 4am. Lowering the sensitivity three
  times did not fix it, because a cat at two metres and a person at eight look identical to a PIR.
  The only thing that actually discriminates is **geometry** — masking the bottom of the lens.
- Silencing one over-eager access log took my journal from **6.1 million to about 400,000 lines
  a day**. I did that *before* deploying log aggregation, which turned a 1 GB/quarter problem
  into a non-problem.
- A single fibre DAC cable failure once cost me four days of "why is the network slow" before I
  thought to look at the cable.

## Why local-first, specifically

Not ideology — I just keep getting burned.

Every camera in the house does its object detection **on my GPU**, on my LAN. I dropped a cheap
outdoor camera I'd already bought, purely because it had no local RTSP stream and no path to one.
The language model that answers questions about the house runs **on the same GPU**, next to the
NVR, and the two of them fight over 11 GB of VRAM — which I consider an acceptable price for
neither of them phoning home.

The rule is simple: **if it stops working when the internet does, it doesn't go in the house.**
Which turns out to be a design constraint and not a limitation. The lighting automation has no
cloud dependency, so it works during an outage. The energy meters speak Modbus over RS485, a
protocol from 1979 that will outlive every vendor cloud I could have chosen instead. And the
sensor history lives in a database with no retention limit, because "we're sunsetting this
product" is a sentence I'd rather not hear about my own house.

The corollary is that I have to fix everything myself. That's the part I enjoy.

## Reach me

Open an issue on any of the repos — that's the most reliable way.
