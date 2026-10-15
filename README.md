# Real Flame Element Mk2 — Home Assistant custom integration

Local TCP control of the Millec / Real Flame MKII Wi‑Fi module (Silicon Labs WGM110) using the ASCII `MWIL` protocol reverse-engineered from `com.millec.realflamethermostatmkii`.

**Not installed into HA yet.** Copy `custom_components/real_flame` into HA config when Brad approves.

See [PROTOCOL.md](PROTOCOL.md) for frame formats. Live status captures: `captures/mwil10.json`.

## Safety

- Default **auto-off after 3 hours** (configurable; 0 disables).
- Optional **block turn-on** (status only).

## Tests

```bash
pip install pytest
pytest -q tests/
```

## Install via HACS

Add custom repository `https://github.com/bradzacher/homeassistant-realflame` (category: Integration).
