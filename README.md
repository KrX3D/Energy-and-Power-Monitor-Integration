# Energy and Power Monitor Integration

A Home Assistant integration to group energy and power sensors for rooms or smart meter devices. This integration allows you to track the values of grouped entities and monitor untracked power consumption.

---

### Introduction

Hello! This is my first integration and my first GitHub repository, so please bear with me as I'm still learning to manage everything in Github. I'm open to any ideas to improve this integration and would greatly appreciate any help with identifying and fixing issues.

---

### Home Assistant Card for this Integration:

[Energy and Power Monitor Card](https://github.com/KrX3D/Energy-and-Power-Monitor-Card).

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

### Step 1: Create a new room (power or energy)
Choose **Power** or **Energy** and set a room name (e.g., *Living Room*).

### Step 2: Add entities, optional smart meter, and included rooms
You can configure three things:

- **Entities**
  - Select the entities that belong to this room.
  - The integration will create a sensor that sums them up.

- **Smart Meter Device (optional)**
  - Choose an optional smart meter for that room.
  - The untracked sensor will show:  
    `smart_meter_value - sum_of_selected_entities`

- **Created Rooms (optional)**
  - Pick one or more already‑created rooms to create a hierarchy.
  - This lets you build nested rooms like *House → Floor → Room*.

---

## Example Hierarchy (Nested Rooms)

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

### Example: A Whole‑House Summary
1. Create *Living Room*, *Kitchen*, and *Bathroom* rooms with their own entities.
2. Create a new room called *House*.
3. In **Created Rooms**, select *Living Room*, *Kitchen*, and *Bathroom*.
4. The *House* sensor will now represent the sum of those rooms.

---

### What Does This Integration Do?

> _More information will be added soon._

- This integration allows you to create multiple groups for your energy and power sensors.
- Most dropdown boxes are filtered to avoid duplicate selections. For example, once an energy/power sensor is added to one integration entity, it will no longer appear for selection until it is unselected.
- The initial GUI allows you to choose between "Energy" and "Power", filtering the entities available in the second GUI.

**Second GUI:**
- **Entities:**
  - Select the energy/power entities for a specific room (e.g., the Living Room).
  - A sensor will be created that combines all selected energy/power values. For example: "Living Room - Power".
- **Smart Meter Device:**
  - You can optionally select a Smart Meter for the room (e.g., Living Room) or leave it as "None". The value of the selected Smart Meter will be subtracted from the sum of the 
    selected entities in that room. The difference will be stored in a second sensor, such as "Untracked - Power".
  - If you have created more rooms/subrooms, they will appear under **Created Rooms**.
  - Selecting a room will aggregate the values from sensors like "Living Room - Power" and "Untracked - Power" (if present).

- You can build a hierarchical view, where the topmost entity aggregates all the values from sub-entities.  
  This way, you can monitor which device or room consumes how much energy or power.

---

## Devices & Entities created

When you add a room, the integration creates:

- **Room sensor** (example: `sensor.energy_power_monitor_living_room_power`)
  - Sum of all selected entities.

- **Untracked sensor** (optional, if smart meter is selected)
  - Shows the difference between the smart meter and the tracked entities.
  - Example: `sensor.energy_power_monitor_living_room_untracked_power`

---

## Tips & Best Practices

- Use **Power** for live consumption (W) and **Energy** for accumulated usage (kWh).
- Build your hierarchy from the bottom up (devices → rooms → floors → house).
- Smart meters are optional, but helpful for identifying “unknown” consumption.
