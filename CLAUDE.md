# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

An [Indigo](https://www.indigodomo.com/) home automation plugin that bridges Indigo devices to [Home Assistant](https://www.home-assistant.io/) entities. The plugin runs inside the Indigo server process on macOS and communicates with HA exclusively via the HA WebSocket API.

## Plugin Structure

Indigo plugins are macOS-style bundle directories (`.indigoPlugin`). The relevant contents:

```
HomeAssistantAgent.indigoPlugin/Contents/
  Info.plist                  ← plugin metadata and version (PluginVersion key)
  Server Plugin/
    plugin.py                 ← all plugin logic (single file)
    requirements.txt          ← zeroconf, websocket-client
    Devices.xml               ← Indigo device type definitions and UI
    Actions.xml               ← Indigo action definitions and UI
    Events.xml                ← Indigo trigger event definitions
    MenuItems.xml             ← plugin menu items
    PluginConfig.xml          ← plugin-level preferences UI
  Packages/                   ← vendored dependencies (pip-installed into here)
```

There is no build step. The plugin runs directly from this directory tree inside the Indigo server.

## Development Environment

Indigo plugins run inside the Indigo macOS application. There is no local test runner — to test changes, install the plugin into Indigo and exercise it through the Indigo UI or its REST/script API.

The `indigo` module is only available at runtime inside Indigo; imports like `import indigo` will fail outside that environment.

To install/update vendored packages into `Contents/Packages/`:
```bash
pip install --target "HomeAssistantAgent.indigoPlugin/Contents/Packages" -r "HomeAssistantAgent.indigoPlugin/Contents/Server Plugin/requirements.txt"
```

## Architecture

### Threading Model

The plugin runs two threads:
1. **Indigo main thread** — runs `runConcurrentThread()` which calls `message_handler()` every 100ms to drain the queue.
2. **WebSocket thread** — `ws_client()` runs `WebSocketApp.run_forever()` in a loop with exponential backoff reconnect. Incoming messages are pushed onto a `Queue` in `on_message()`.

This queue-based hand-off is intentional: WebSocket callbacks must not call Indigo API methods directly because Indigo is not thread-safe.

### State Model

- `ha_entity_map: dict[str, dict[str, entity]]` — nested by entity type then entity name. `entity_type.entity_name` is the HA entity ID format (e.g., `light.kitchen`).
- `entity_devices: dict[str, int]` — maps HA entity_id to Indigo device ID. Populated by `deviceStartComm`.
- `custom_states: dict[int, list]` — maps Indigo device ID to a list of dynamic state keys (HA attributes become custom Indigo states). Triggers `stateListOrDisplayStateIdChanged()` when the set changes.
- `battery_entities: dict[int, str]` — maps Indigo device ID to the HA entity_id of its battery sensor.

### HA → Indigo Update Flow

All state updates flow through `entity_update(entity_id, entity)`:
1. Updates `ha_entity_map`.
2. Looks up the corresponding Indigo device via `entity_devices`.
3. Skips if `last_updated` timestamp is unchanged (unless `force_update=True`).
4. Writes HA attributes as custom device states.
5. Dispatches into device-type-specific logic to update Indigo's built-in states (e.g., `onOffState`, `brightnessLevel`, thermostat setpoints).

### Indigo → HA Command Flow

Action callbacks (e.g., `actionControlDimmerRelay`, `actionControlThermostat`) build a `call_service` dict and call `send_ws()`. `send_ws()` increments `last_sent_id`, records the message in `sent_messages`, and sends JSON on the WebSocket. The `result` handler in `process_message()` matches responses back by ID.

### WebSocket Lifecycle

On `auth_ok`:
1. Subscribes to `state_changed` and `automation_triggered` events.
2. Sends `get_config` and `get_states` to populate initial state.

### Device Type Mapping

| HA domain      | Indigo type      | XML id            |
|---------------|-----------------|-------------------|
| climate        | Thermostat       | `HAclimate`       |
| light          | Dimmer           | `HAdimmerType`    |
| switch         | Relay            | `HAswitchType`    |
| binary_sensor  | Sensor (on/off)  | `HAbinarySensorType` |
| sensor         | Sensor (value)   | `HAsensor`        |
| cover          | Relay            | `ha_cover`        |
| lock           | Relay/Lock       | `ha_lock`         |
| fan            | SpeedControl     | `ha_fan`          |
| media_player   | Dimmer           | `ha_media_player` |
| (any other)    | Custom           | `ha_generic`      |

Device capabilities (e.g., `SupportsSetPosition`, `SupportsHvacFanMode`) are stored as `pluginProps` and set dynamically in `deviceStartComm` based on the HA entity's `supported_features` bitmask.

### Triggers

Two trigger types defined in `Events.xml`:
- `automationEvent` — fires when HA emits an `automation_triggered` event.
- `connection_event` — fires on WebSocket connect/disconnect/error.

## Releasing

Releases are automated via GitHub Actions:
1. Update `PluginVersion` in `HomeAssistantAgent.indigoPlugin/Contents/Info.plist`.
2. Push to `main` or `master`. The workflow creates a GitHub release tagged `v<version>` and attaches a `.indigoPlugin.zip`.
3. PRs to `main`/`master` are blocked if the version tag already exists (enforced by `version-check.yml`).

The zip excludes `.pyc`, `__pycache__`, `.idea`, and `Contents/Packages/` (vendored deps are not distributed).

## Key Conventions

- All outbound HA commands use the `call_service` WebSocket message type. The `domain` and `service` keys match HA service names exactly.
- The `address` field of an Indigo device stores the full HA entity ID (e.g., `light.kitchen`).
- Dynamic HA entity attributes beyond the standard ones become custom Indigo device states via `getDeviceStateList`/`custom_states`.
- Deprecated actions (older individual action IDs replaced by consolidated `*_actions` actions) are kept with `uiPath="hidden"` in `Actions.xml` for backward compatibility with existing Indigo action groups.