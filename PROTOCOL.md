# Real Flame Element Mk2 — local TCP protocol (Millec / Intelligy)

Derived from decompiled Android app `com.millec.realflamethermostatmkii` (classes under `com.intelligy.millec.intelligythermostatmkii`), especially `ModulatingValve.java`, `TCPClient.java`, `AppSettings.java`, `AppDefines.java`, `WGM110Control.java`.

Validated against live device **192.168.1.108:3000** (Silicon Labs WGM110, OUI 60:ef:ab) on 15 Oct 2026 using **read-only** `MWIL10` queries only.

## Transport

| Item | Value |
|---|---|
| Host | Fireplace Wi‑Fi module IP (after app onboarding) |
| Port | **3000** TCP (`WIFI_TCP_PORT`, `AP_MODE_DEFAULT_PORT`) |
| Framing | Raw ASCII bytes, **no newline required**, no length prefix, no auth |
| Session | Short-lived: connect → write → read (optional) → close |
| Setup AP | SSID `Millec_ID_AP`, IP `10.0.0.1:3000` (onboarding only) |
| App TCP timeout | ~3 s read loop (`TCPClient`) |

UDP discovery (not required for HA once IP known): broadcast `MWI070011` to **UDP 3001**; responses `MWI03` / `MWI05` / `MWI07` carry MAC / valve ID.

## Operating modes (`currentMode` / `mvOpState`)

From `ModulatingValve` constants + `AppSettings` setters:

| Value | Constant | Meaning |
|---|---|---|
| **0** | `STATE_MANUAL_MODE_TEMP` | Manual temperature control |
| **1** | `STATE_MANUAL_MODE_FLAME` | Manual flame height |
| **2** | `STATE_TIMER_MODE` | Auto / timer (`setModeAuto`) |
| **3** | `STATE_EX_MANAGED_MODE` | Externally managed (seen live; cloud/external) |
| **4** | `STATE_OFF` | Off (`setModeOff`; default in app) |

## Value ranges (`AppSettings`)

| Field | Min | Max | Notes |
|---|---|---|---|
| Temperature level | **10** | **35** | °C (app treats as integer °C) |
| Flame level | **1** | **7** | Manual flame steps |
| LED R/G/B | 0–255 stored; status parse multiplies by 2 when reading |

## Status request (safe / read-only)

```
MWIL10
```

Send as ASCII. Device replies with a single ASCII CSV line (often trailing comma).

### Live captures (identical ×3)

```
MWIL11,14,01,D1B4B025,16,00,03,00,01,0E,0E,01,00,00,00,
```

### Status response parse (`processRXTCPData`)

1. Require prefix starting with `MWI`.
2. `str.substring(3, 5) == "L1"` → status frame (matches both `MWIL1…` and `MWIL11…`).
3. `parts = str.split(",")` — need **≥ 12** fields (indices 0–11).
4. Fields **1,2,4–11** (and optional 12–14) are integers parsed as **hex** (`Integer.parseInt(s, 16)`).

| Index | APK variable | Live example | Decoded |
|---|---|---|---|
| 0 | prefix | `MWIL11` | Status type |
| 1 | `mvTempSetting` | `14` | **20 °C** setpoint |
| 2 | `mvFlameSetting` | `01` | flame setting **1** |
| 3 | clock echo / opaque | `D1B4B025` → after local control `030F3206` | After **local** MWIL20, echoes last control clock as 8 hex chars `DDHHMMSS` (no separators). Under external/cloud management, opaque (e.g. `D1B4B025`). APK does not parse this field. |
| 4 | `mvTempReading` | `16` | **22 °C** room/sensor |
| 5 | `mvState` | `00` | state **0** |
| 6 | `mvOpState` | `03` | mode **3** ex_managed |
| 7 | `mvCurrentFlameSetting` | `00` | current flame **0** (burner idle) |
| 8 | `mvCurrentFanLevel` | `01` | fan **1** |
| 9 | `mvAutoTimerSlot` | `0E` | **14** |
| 10 | `mvAutoTimeDay` | `0E` | **14** |
| 11 | `WiFiModuleToModValveCommsStatus` | `01` | **1** (OK) |
| 12–14 | LED R,G,B | `00,00,00` | stored as value×2 → 0,0,0 |

## Control request (DO NOT SEND without approval)

Built by `GetLocalControlSendCommandRequest()`:

```
MWIL20 + MM + TT + FF + DD + HH + NN + SS + RR + GG + BB
```

Every field after `MWIL20` is **two uppercase hex digits** (`%02X`), concatenated with **no separators**.

| Field | Source |
|---|---|
| `MM` | mode (`getCurrentMode()`): 00/01/02/04 (and 03 if externally set) |
| `TT` | temperature level 10–35 |
| `FF` | flame level 1–7 |
| `DD` | `Date.getDay() - 1` (Java: 0=Sun … 6=Sat → then minus 1 — legacy `Date` API) |
| `HH` | hours 0–23 |
| `NN` | minutes |
| `SS` | seconds |
| `RR`,`GG`,`BB` | LED channels from settings (often 00) |

Example **off** (mode 4, temp 20, flame 1, clock/LED zeroed for illustration):

```
MWIL2004140100000000000000
```

Breakdown: `MWIL20` + `04` + `14` + `01` + `00` + `00` + `00` + `00` + `00` + `00` + `00`

Example **manual temperature on** at 20 °C, flame 1:

```
MWIL20001401…(clock+LED)…
```

i.e. `MM=00`, `TT=14`, `FF=01`.

### Control ACK (live, 15 Oct 2026)

Every MWIL20 received a short ASCII ACK (not a status frame):

```
MWIL2,
```

No status payload in the ACK. Confirm mode with a separate `MWIL10` after **≥1.5–2 s** (status can lag; first poll ~0.8 s after OFF still showed prior `op_state=3`, second poll showed `04`).

### Field 3 clock echo (live)

After successful local control, status field 3 becomes the control clock bytes as 8 hex digits. Example: frame `MWIL20041401030F3206…` → status `…,030F3206,…` (Thu Java-day field `03`, 15:50:06 Adelaide). Validates day encoding: Thu 2026-10-15 → Java day 4 → field `(4-1)=3`.

### Manual temp + flame behaviour (live)

ON `mode=00` @ setpoint 20 °C while room read 22 °C: `op_state` became **0** within ~6 s, but `current_flame` stayed **0** for the full ~56 s poll window (thermostat not calling for heat). Control of **mode** is confirmed; burner ignition not observed in this condition.

## Cloud (reference only)

- Hosts: `milleciot.com`, `milleciotd.com`
- `GET /MODV_V02/mvapi.php?DEV=AND&FXN=…&PL=…` with encrypted payload
- FXNs include A01 auth, R01 register, C01 device, S03/S04 status
- Not used by this local integration

## Timing recommendations for HA

| Operation | Timeout |
|---|---|
| TCP connect + write | 3–5 s |
| Status read after `MWIL10` | 0.5–2 s (live ~0.5–1.3 s) |
| Control ACK `MWIL2,` | ~0.5–0.8 s |
| Status settle after MWIL20 | **1.5–2.5 s** (poll until op_state matches; may need 2nd poll) |
| Poll interval | 30–60 s |
| Serialize all TCP with an asyncio lock | required |

## Safety (integration policy)

- Configurable **auto-off** (default **3 hours**) after any non-off mode.
- Optional **block turn-on** (status/monitoring only).
- Never send control frames unless user turns climate/mode on and turn-on is allowed.

## Live burner test (15 Oct 2026, 15:58 Adelaide)

ON `MWIL20001901030F3A27000000` (mode 00, 25 °C, room 22 °C):
- +6 s: `mvState`(f5)=01, current_flame=1, fan=0 (ignition)
- +11 s onward: current_flame=5, fan=3, steady
- Field 5 `mvState` = 01 while burner running, 00 when idle/off → good "burning" indicator alongside current_flame>0.
OFF `MWIL20041401030F3B29000000` → op=04, flame=0, fan=1 within 2 s.
