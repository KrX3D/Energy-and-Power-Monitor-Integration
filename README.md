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

### Step 1: Create a new zone (power or energy)
Choose **Power** or **Energy** and set a zone name (e.g., *Living Room*).

### Step 2: Add entities, optional smart meter, and included zones
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
  - Zones already assigned to another parent zone are hidden from the list.

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