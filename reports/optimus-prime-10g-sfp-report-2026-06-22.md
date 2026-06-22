# Optimus Prime — 10G SFP+ Port Investigation Report
**Date:** 2026-06-22  
**Reported by:** Matteo Favaro  
**Issue:** Dream Machine SFP+ port suspected faulty — open incident with Ubiquiti

---

## Environment

| Component | Details |
|---|---|
| Server | Optimus Prime (Arch Linux) |
| Server NIC | Aquantia AQC100, driver `atlantic`, firmware 3.1.77 |
| Server interface | `enp7s0` — SFP+ 10G (`192.168.1.10`) |
| Server interface | `enp6s0` — Copper 1G (`192.168.1.13`) |
| DAC Cable | SwissGBIC SFP-H10GB-CU5M-C, 5m passive copper |
| DAC Serial | SG2309260081 (manufactured 2023-09-27) |
| Router | UniFi Dream Machine (`192.168.1.1`) |
| ISP | Salt Mobile — multi-gigabit fiber (~7 Gbps plan) |

All iperf3 tests were run with `-B 192.168.1.10` to explicitly bind traffic to `enp7s0` (SFP+ 10G interface), eliminating the 1G copper fallback path.

---

## DAC Cable Verification (`ethtool -m enp7s0`)

```
Identifier                                : 0x03 (SFP)
Extended identifier                       : 0x04 (GBIC/SFP defined by 2-wire interface ID)
Connector                                 : 0x21 (Copper pigtail)
Transceiver codes                         : 0x00 0x00 0x00 0x00 0x00 0x04 0x00 0x00 0x00
Transceiver type                          : Passive Cable
Encoding                                  : 0x00 (unspecified)
BR Nominal                                : 10300MBd
Rate identifier                           : 0x00 (unspecified)
Length (SMF)                              : 0km
Length (OM2)                              : 0m
Length (OM1)                              : 0m
Length (Copper or Active cable)           : 5m
Length (OM3)                              : 0m
Passive Cu cmplnce.                       : 0x01 (SFF-8431 appendix E)
Vendor name                               : SwissGBIC
Vendor OUI                                : 00:02:c9
Vendor PN                                 : SFP-H10GB-CU5M-C
Vendor rev                                : 09
Vendor SN                                 : SG2309260081
Date code                                 : 230927
```

---

## Link Status (`ethtool enp7s0`)

```
Settings for enp7s0:
    Supported ports: [ FIBRE ]
    Supported link modes:   100baseT/Full
                            1000baseT/Full
                            10000baseT/Full
                            2500baseT/Full
                            5000baseT/Full
    Advertised link modes:  100baseT/Full
                            1000baseT/Full
                            10000baseT/Full
                            2500baseT/Full
                            5000baseT/Full
    Speed: 10000Mb/s
    Duplex: Full
    Auto-negotiation: on
    Port: FIBRE
    Link detected: yes
```

The NIC reports 10,000 Mb/s full duplex — the link negotiation appears healthy at the OS level.

---

## Test 1 — LAN: Optimus Prime ↔ Dream Machine SFP+ port

**Server:** `192.168.1.1:5201`  
**Client bound to:** `192.168.1.10` (enp7s0, SFP+)

### TX — Optimus Prime → Dream Machine

```
Connecting to host 192.168.1.1, port 5201
[  5] local 192.168.1.10 port 49641 connected to 192.168.1.1 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-1.00   sec   114 MBytes   956 Mbits/sec    0    314 KBytes
[  5]   1.00-2.00   sec   111 MBytes   933 Mbits/sec    0   1007 KBytes
[  5]   2.00-3.00   sec   113 MBytes   947 Mbits/sec    0    600 KBytes
[  5]   3.00-4.00   sec   111 MBytes   934 Mbits/sec    0    249 KBytes
[  5]   4.00-5.00   sec   110 MBytes   918 Mbits/sec    0    382 KBytes
[  5]   5.00-6.00   sec   110 MBytes   924 Mbits/sec    0    362 KBytes
[  5]   6.00-7.00   sec   110 MBytes   924 Mbits/sec    0    503 KBytes
[  5]   7.00-8.00   sec   110 MBytes   922 Mbits/sec    0    235 KBytes
[  5]   8.00-9.00   sec   112 MBytes   936 Mbits/sec  1738    679 KBytes
[  5]   9.00-10.00  sec   110 MBytes   924 Mbits/sec    0    781 KBytes
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  1.09 GBytes   932 Mbits/sec  1738   sender
[  5]   0.00-10.00  sec  1.06 GBytes   912 Mbits/sec         receiver
```

**Result: 932 Mbps — hard cap at ~1G despite 10G link negotiation. 1,738 retransmits.**

### RX — Dream Machine → Optimus Prime

```
Connecting to host 192.168.1.1, port 5201
Reverse mode, remote host 192.168.1.1 is sending
[  5] local 192.168.1.10 port 34071 connected to 192.168.1.1 port 5201
[ ID] Interval           Transfer     Bitrate
[  5]   0.00-1.00   sec   312 MBytes  2.61 Gbits/sec
[  5]   1.00-2.00   sec   353 MBytes  2.96 Gbits/sec
[  5]   2.00-3.00   sec   123 MBytes  1.03 Gbits/sec
[  5]   3.00-4.00   sec   112 MBytes   936 Mbits/sec
[  5]   4.00-5.00   sec   112 MBytes   939 Mbits/sec
[  5]   5.00-6.00   sec   111 MBytes   928 Mbits/sec
[  5]   6.00-7.00   sec   112 MBytes   940 Mbits/sec
[  5]   7.00-8.00   sec   175 MBytes  1.47 Gbits/sec
[  5]   8.00-9.00   sec   332 MBytes  2.78 Gbits/sec
[  5]   9.00-10.00  sec   340 MBytes  2.85 Gbits/sec
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  2.03 GBytes  1.75 Gbits/sec  3356   sender
[  5]   0.00-10.00  sec  2.03 GBytes  1.74 Gbits/sec         receiver
```

**Result: 1.75 Gbps average — wildly unstable, oscillating between 936 Mbps and 2.96 Gbps. 3,356 retransmits.**

---

## Test 2 — External: Optimus Prime ↔ init7 (`speedtest.init7.net`)

**Server:** `speedtest.init7.net:5201` (82.197.188.129, Zurich)  
**Client bound to:** `192.168.1.10` (enp7s0, SFP+)

### TX — Optimus Prime → init7

```
Connecting to host speedtest.init7.net, port 5201
[  5] local 192.168.1.10 port 35773 connected to 82.197.188.129 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-1.00   sec   555 MBytes  4.65 Gbits/sec    0   6.45 MBytes
[  5]   1.00-2.00   sec   552 MBytes  4.63 Gbits/sec    0   5.98 MBytes
[  5]   2.00-3.00   sec   525 MBytes  4.40 Gbits/sec    0   7.74 MBytes
[  5]   3.00-4.00   sec   531 MBytes  4.45 Gbits/sec    0   6.32 MBytes
[  5]   4.00-5.00   sec   566 MBytes  4.75 Gbits/sec    0   7.83 MBytes
[  5]   5.00-6.00   sec   542 MBytes  4.55 Gbits/sec    0   6.49 MBytes
[  5]   6.00-7.00   sec   548 MBytes  4.59 Gbits/sec    0   6.36 MBytes
[  5]   7.00-8.00   sec   522 MBytes  4.38 Gbits/sec    0   6.44 MBytes
[  5]   8.00-9.00   sec   534 MBytes  4.48 Gbits/sec    0   7.74 MBytes
[  5]   9.00-10.00  sec   506 MBytes  4.24 Gbits/sec    0   6.42 MBytes
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  5.26 GBytes  4.52 Gbits/sec    0   sender
[  5]   0.00-10.01  sec  5.21 GBytes  4.47 Gbits/sec       receiver
```

**Result: 4.52 Gbps sustained — rock stable, zero retransmits.**

### RX — init7 → Optimus Prime

```
Connecting to host speedtest.init7.net, port 5201
Reverse mode, remote host speedtest.init7.net is sending
[  5] local 192.168.1.10 port 33695 connected to 82.197.188.129 port 5201
[ ID] Interval           Transfer     Bitrate
[  5]   0.00-1.00   sec  8.88 MBytes  74.4 Mbits/sec
[  5]   1.00-2.00   sec  7.88 MBytes  66.1 Mbits/sec
[  5]   2.00-3.00   sec  28.2 MBytes   237 Mbits/sec
[  5]   3.00-4.00   sec  20.4 MBytes   171 Mbits/sec
[  5]   4.00-5.00   sec  5.50 MBytes  46.1 Mbits/sec
[  5]   5.00-6.00   sec  3.88 MBytes  32.5 Mbits/sec
[  5]   6.00-7.00   sec  4.75 MBytes  39.8 Mbits/sec
[  5]   7.00-8.00   sec  24.0 MBytes   201 Mbits/sec
[  5]   8.00-9.00   sec  48.0 MBytes   403 Mbits/sec
[  5]   9.00-10.00  sec  74.0 MBytes   621 Mbits/sec
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.01  sec   227 MBytes   191 Mbits/sec   71   sender
[  5]   0.00-10.00  sec   226 MBytes   189 Mbits/sec        receiver
```

**Result: 191 Mbps average — highly unstable, climbing from 32 Mbps to 621 Mbps over 10 seconds. 71 retransmits.**

---

## Test 3 — Flow Control Comparison (LAN, DM SFP+ port)

Ubiquiti support requested a comparison with the DM global switch **Flow Control** setting toggled on and off.  
Flow control was toggled via the UniFi API (`/proxy/network/api/s/default/set/setting/global_switch`).  
All tests bound to `192.168.1.10` (enp7s0, SFP+).

### Flow Control OFF (default state)

**TX — Optimus Prime → Dream Machine**
```
[  5] local 192.168.1.10 port 53043 connected to 192.168.1.1 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-1.00   sec   117 MBytes   978 Mbits/sec    0    223 KBytes
[  5]   1.00-2.00   sec   111 MBytes   929 Mbits/sec    0    942 KBytes
[  5]   2.00-3.00   sec   109 MBytes   918 Mbits/sec    0    447 KBytes
[  5]   3.00-4.00   sec   112 MBytes   942 Mbits/sec    0    962 KBytes
[  5]   4.00-5.00   sec   110 MBytes   925 Mbits/sec    0    286 KBytes
[  5]   5.00-6.00   sec   114 MBytes   955 Mbits/sec    0    283 KBytes
[  5]   6.00-7.00   sec   110 MBytes   924 Mbits/sec    0    766 KBytes
[  5]   7.00-8.00   sec   110 MBytes   925 Mbits/sec    0    240 KBytes
[  5]   8.00-9.00   sec   109 MBytes   916 Mbits/sec    0    365 KBytes
[  5]   9.00-10.00  sec   113 MBytes   946 Mbits/sec    0    303 KBytes
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  1.09 GBytes   936 Mbits/sec    0   sender
[  5]   0.00-10.00  sec  1.08 GBytes   929 Mbits/sec       receiver
```

**RX — Dream Machine → Optimus Prime**
```
[  5] local 192.168.1.10 port 48323 connected to 192.168.1.1 port 5201
[ ID] Interval           Transfer     Bitrate
[  5]   0.00-1.00   sec   343 MBytes  2.87 Gbits/sec
[  5]   1.00-2.00   sec   348 MBytes  2.92 Gbits/sec
[  5]   2.00-3.00   sec   273 MBytes  2.29 Gbits/sec
[  5]   3.00-4.00   sec   112 MBytes   938 Mbits/sec
[  5]   4.00-5.00   sec   112 MBytes   938 Mbits/sec
[  5]   5.00-6.00   sec   112 MBytes   940 Mbits/sec
[  5]   6.00-7.00   sec   110 MBytes   923 Mbits/sec
[  5]   7.00-8.00   sec   111 MBytes   933 Mbits/sec
[  5]   8.00-9.00   sec  99.4 MBytes   834 Mbits/sec
[  5]   9.00-10.00  sec   327 MBytes  2.75 Gbits/sec
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.01  sec  1.90 GBytes  1.63 Gbits/sec  2722   sender
[  5]   0.00-10.00  sec  1.90 GBytes  1.63 Gbits/sec         receiver
```

### Flow Control ON

**TX — Optimus Prime → Dream Machine**
```
[  5] local 192.168.1.10 port 35171 connected to 192.168.1.1 port 5201
[ ID] Interval           Transfer     Bitrate         Retr  Cwnd
[  5]   0.00-1.00   sec   113 MBytes   949 Mbits/sec    0    286 KBytes
[  5]   1.00-2.00   sec   106 MBytes   888 Mbits/sec    0   1.04 MBytes
[  5]   2.00-3.00   sec   116 MBytes   977 Mbits/sec    0   1.49 MBytes
[  5]   3.00-4.00   sec   111 MBytes   932 Mbits/sec    0   1.30 MBytes
[  5]   4.00-5.00   sec   114 MBytes   953 Mbits/sec    0    438 KBytes
[  5]   5.00-6.00   sec   108 MBytes   905 Mbits/sec    0    656 KBytes
[  5]   6.00-7.00   sec   111 MBytes   930 Mbits/sec    0    387 KBytes
[  5]   7.00-8.00   sec   106 MBytes   888 Mbits/sec    0    221 KBytes
[  5]   8.00-9.00   sec   111 MBytes   928 Mbits/sec    0    331 KBytes
[  5]   9.00-10.00  sec   111 MBytes   929 Mbits/sec    0    515 KBytes
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  1.08 GBytes   928 Mbits/sec    0   sender
[  5]   0.00-10.00  sec  1.07 GBytes   917 Mbits/sec       receiver
```

**RX — Dream Machine → Optimus Prime**
```
[  5] local 192.168.1.10 port 45739 connected to 192.168.1.1 port 5201
[ ID] Interval           Transfer     Bitrate
[  5]   0.00-1.00   sec   346 MBytes  2.90 Gbits/sec
[  5]   1.00-2.00   sec   318 MBytes  2.67 Gbits/sec
[  5]   2.00-3.00   sec   213 MBytes  1.78 Gbits/sec
[  5]   3.00-4.00   sec   112 MBytes   939 Mbits/sec
[  5]   4.00-5.00   sec   251 MBytes  2.11 Gbits/sec
[  5]   5.00-6.00   sec   325 MBytes  2.73 Gbits/sec
[  5]   6.00-7.00   sec   343 MBytes  2.88 Gbits/sec
[  5]   7.00-8.00   sec   267 MBytes  2.24 Gbits/sec
[  5]   8.00-9.00   sec   111 MBytes   930 Mbits/sec
[  5]   9.00-10.00  sec   233 MBytes  1.95 Gbits/sec
- - - - - - - - - - - - - - - - - - - - - - - - -
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  2.46 GBytes  2.11 Gbits/sec  4540   sender
[  5]   0.00-10.00  sec  2.46 GBytes  2.11 Gbits/sec         receiver
```

### Flow Control Comparison

| Direction | FC OFF — Bitrate | FC OFF — Retr | FC ON — Bitrate | FC ON — Retr |
|---|---|---|---|---|
| TX OP→DM | 936 Mbps | 0 | 928 Mbps | 0 |
| RX DM→OP | 1.63 Gbps avg | 2,722 | 2.11 Gbps avg | **4,540** |

**Result: No meaningful improvement.** TX remains hard-capped at ~1 Gbps in both cases. RX average increased marginally with FC ON but retransmits worsened significantly (2,722 → 4,540). Flow control does not address the underlying port fault.  
DM global switch setting restored to `flowctrl_enabled: false` after testing.

---

## Summary

| Test | Direction | Bitrate | Retransmits | Notes |
|---|---|---|---|---|
| LAN (DM) | TX OP→DM | 932 Mbps | 1,738 | Hard 1G cap despite 10G link |
| LAN (DM) | RX DM→OP | 1.75 Gbps avg | 3,356 | Oscillates 936M–2.96G |
| External (init7) | TX OP→init7 | **4.52 Gbps** | **0** | Stable — NIC & ISP healthy |
| External (init7) | RX init7→OP | 191 Mbps avg | 71 | Unstable, climbing trend |
| LAN FC OFF | TX OP→DM | 936 Mbps | 0 | Same 1G cap |
| LAN FC OFF | RX DM→OP | 1.63 Gbps avg | 2,722 | Same instability |
| LAN FC ON | TX OP→DM | 928 Mbps | 0 | No change |
| LAN FC ON | RX DM→OP | 2.11 Gbps avg | 4,540 | More retransmits |

---

## Analysis

**The Aquantia AQC100 NIC and Salt fiber uplink are both healthy.**  
The init7 TX result — 4.52 Gbps sustained with zero retransmits — proves the server NIC, DAC cable, and ISP uplink are all functioning correctly.

**The fault is on the Dream Machine SFP+ port.**

- TX to the DM is capped at ~1 Gbps despite `ethtool` reporting a 10,000 Mb/s negotiated link. This suggests the DM SFP+ port is forwarding/throttling at 1G speeds internally.
- RX from the DM is erratic with thousands of retransmits — consistent with an intermittent SFP+ transceiver or switching fabric fault on the DM side.
- RX from init7 (which travels inbound through the DM SFP+ port) shows the same instability, confirming the DM is the common failure point in the inbound path.
- Toggling Flow Control had no meaningful effect — the fault is hardware-level.

**History:** The original DAC cable (replaced 2026-06-19 after physical failure) was confirmed as the cause of the initial outage. After replacement with a new SwissGBIC SFP-H10GB-CU5M-C DAC, the link negotiates at 10G but throughput remains degraded, pointing to the DM SFP+ port hardware as the remaining fault.
