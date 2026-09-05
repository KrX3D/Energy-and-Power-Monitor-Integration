# Energy and Power Monitor Integration

A Home Assistant integration to group energy and power sensors for zones or smart meter devices. This integration allows you to track the values of grouped entities and monitor untracked power consumption.

---

### Introduction

Hello! This is my first integration and my first GitHub repository, so please bear with me as I'm still learning to manage everything in Github. I'm open to any ideas to improve this integration and would greatly appreciate any help with identifying and fixing issues.

---

### Home Assistant Card for this Integration:

[Energy and Power Monitor Card](https://github.com/KrX3D/Energy-and-Power-Monitor-Card).

---

## Requirements

- Home Assistant **2026.3.0** or newer

---

## Installation

### HACS (recommended)
1. Open **HACS → Integrations** in Home Assistant.
2. Add the repository as a **Custom repository**:
   - URL: `https://github.com/KrX3D/Energy-and-Power-Monitor-Integration`
   - Category: **Integration**
3. Install **Energy and Power Monitor Integration**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration** and search for **Energy and Power Monitor**.

### Manual install
1. Copy the `custom_components/energy_power_monitor` directory into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Energy and Power Monitor**.

---

## Configuration Overview

### Step 1: Choose what to do
When you click **Add Integration** (or **Add Entry** on an existing integration), you're asked to pick one of:
- **Add a new zone** — the zone workflow described below.
- **Manage excluded entities** — see [Excluded Entities](#excluded-entities).

### Step 2: Create a new zone (power or energy)
Choose **Power** or **Energy** and set a zone name (e.g., *Living Room*). A **Hide from Included Zones** checkbox sits right next to the zone name — turn it on for a zone that should never be offered as a sub-zone of another (typically your topmost/whole-house zone in a nested hierarchy). It can also be toggled later from the zone's **Reconfigure** screen.

### Step 3: Add entities, optional smart meter, and included zones
You can configure three things:

- **Entities**
  - Select the entities that belong to this zone.
  - The integration will create a sensor that sums them up.
  - The dropdown is filtered: only sensors of the correct type (`_power` or `_energy`) are shown, and sensors already assigned to another zone are hidden.

- **Smart Monitor (optional)**
  - Choose an optional smart meter for that zone.
  - Leave it empty if you don't need untracked consumption monitoring.
  - The untracked sensor will show:  
    `smart_meter_value - sum_of_selected_entities`

- **Included Zones (optional)**
  - Pick one or more already‑created zones to create a hierarchy.
  - This lets you build nested zones like *House → Floor → Zone*.
  - Zones already assigned to another parent zone, and any zone with **Hide from Included Zones** turned on, are hidden from the list.
  - A zone never appears in its own picker, so it can't be included as its own sub-zone.

---

## Excluded Entities

Sometimes a sensor's entity ID happens to end in `_power` or `_energy` without actually being a real consumption sensor you want to track (e.g. `sensor.heating_power` could be a target/setpoint helper, not an actual power reading). Rather than remembering to skip it by hand in every zone, you can exclude it globally, once:

1. Go to **Settings → Devices & Services → Add Entry** on the **Energy and Power Monitor** integration (or **Add Integration** if you haven't set up any zone yet).
2. Choose **Manage excluded entities**.
3. Two separate dropdowns are shown — **Power entities to always exclude** and **Energy entities to always exclude** — so you're only ever picking from the type you care about. Select every entity that should never be offered as an Entity or Smart Monitor.

The list to pick from only shows `_power`/`_energy` sensors that are actually still available for selection right now — the same pool the Entities/Smart Monitor dropdowns draw from — not every power/energy entity in your Home Assistant instance. An entity already assigned to a zone or already used as a Smart Monitor won't show up here either, since it's not a candidate anywhere until it's freed up.

This creates a single, dedicated **Excluded Entities** entry that shows up right alongside your zones in the integration's entry list — that's also where you go to edit the list later (click it → **Configure**). Only one such entry can exist; the menu option won't let you create a second one.

Once set:
- Excluded entities disappear from the **Entities** and **Smart Monitor** dropdowns in both the "add zone" and "reconfigure zone" screens, for every zone, power and energy alike.
- Entities already assigned to a zone before being excluded are **not** removed from that zone — exclusion only affects future selection, so existing setups don't silently break.
- The **Excluded Entities** entry itself doesn't create any sensors; it's a settings-only entry.

---

## Example Hierarchy (Nested Zones)

```
HOUSE
├── Living Room
│   ├── Plug Window
│   └── Plug Table
├── Kitchen
│   ├── Device 1
│   └── Device 2
└── Bathroom
    └── Fan
```

## Deep Hierarchy Example (5 Levels)

```
HOUSE
├── Floor 1
│   ├── Living Room
│   │   ├── Corner
│   │   │   ├── Plug Window
│   │   │   └── Plug Table
│   │   └── TV Area
│   │       └── TV Plug
│   └── Kitchen
│       ├── Counter
│       │   └── Device 1
│       └── Fridge
│           └── Device 2
└── Floor 2
    └── Bedroom
        └── Desk
            └── Laptop Plug
```

### Example: A Whole‑House Summary
1. Create *Living Room*, *Kitchen*, and *Bathroom* zones with their own entities.
2. Create a new zone called *House*.
3. In **Included Zones**, select *Living Room*, *Kitchen*, and *Bathroom*.
4. The *House* sensor will now represent the sum of those zones.

---

### What Does This Integration Do?

- This integration allows you to create multiple groups for your energy and power sensors.
- Dropdown boxes are filtered to avoid duplicate selections. Once an energy/power sensor is assigned to a zone it will no longer appear for selection in other zones.
- The initial screen lets you choose between **Energy** and **Power**, which filters the entities available in the next step.
- You can globally block specific entities from ever showing up as candidates — see [Excluded Entities](#excluded-entities).

**Configuration screen:**
- **Entities:**
  - Select the energy/power entities for a specific zone (e.g., the Living Room).
  - A sensor will be created that sums all selected values — for example: `Living Room selected entities - Power`.
- **Smart Monitor:**
  - Optionally select a Smart Meter for the zone. Leave empty if not needed.
  - The value of the selected Smart Meter will be subtracted from the sum of the selected entities. The difference is stored in a second sensor — for example: `Living Room untracked - Power`.
- **Included Zones:**
  - If you have already created zones, they will appear here.
  - Selecting a zone will aggregate its sensor values (including its untracked sensor, if present) into this zone.

- You can build a hierarchical view where the topmost zone aggregates all values from sub-zones, letting you monitor which device or zone consumes how much energy or power.

---

## Resilience

- If a tracked entity is **removed** from Home Assistant, it is automatically dropped from the zone without any manual reconfiguration.
- If a tracked entity is **renamed**, the reference is automatically updated in the zone configuration.
- Both changes are persisted immediately so they survive a restart.

---

## Devices & Entities created

When you add a zone, the integration creates:

- **Zone sensor** (example: `sensor.energy_power_monitor_living_room_power`)
  - Sum of all selected entities.

- **Untracked sensor** (optional, only created when a Smart Monitor is selected)
  - Shows the difference between the smart meter and the tracked entities.
  - Example: `sensor.energy_power_monitor_living_room_untracked_power`

---

## Entity states & attributes (for card developers)

### Zone sensor
**Entity ID pattern**
- `sensor.energy_power_monitor_<zone_name>_<power|energy>`

**Friendly name pattern**
- `<Zone Name> selected entities - <Power|Energy>`

**State**
- The sum of all selected entities (power in W or energy in kWh).

**Attributes**
- `selected_entities`: List of directly assigned entity IDs (does not include entities pulled in via Included Zones).

### Untracked (smart meter) sensor
**Entity ID pattern**
- `sensor.energy_power_monitor_<zone_name>_untracked_<power|energy>`

**Friendly name pattern**
- `<Zone Name> untracked - <Power|Energy>`

**State**
- `smart_meter_value - sum_of_selected_entities`
- Clamped to `0` when negative.

**Attributes**
- `Selected Smart Meter Device`: The smart meter entity ID used for the calculation.
- `Energy and Power Monitor`: The zone sensor entity ID.

---

## Tips & Best Practices

- Use **Power** for live consumption (W) and **Energy** for accumulated usage (kWh).
- Build your hierarchy from the bottom up (devices → zones → floors → house).
- Smart monitors are optional, but helpful for identifying "unknown" consumption.
- Zone names support unicode characters (e.g. accented letters) — the integration normalizes them automatically for entity IDs.
- If a `_power`/`_energy` entity keeps showing up in dropdowns but isn't a real consumption sensor, add it to **Excluded Entities** once instead of skipping it manually in every zone.
- Turn on **Hide from Included Zones** for your topmost/whole-house zone in a nested hierarchy — it has nothing above it to be included in, so keeping it out of every other zone's picker keeps that list shorter and prevents accidental circular nesting.