# Energy and Power Monitor Integration

A Home Assistant integration to group energy and power sensors for rooms or smart meter devices. This integration allows you to track the values of grouped entities and monitor untracked power consumption.

---

### ⚠️ UNDER DEVELOPMENT - STILL TESTING ⚠️

---

### Introduction

Hello! This is my first integration and my first GitHub repository, so please bear with me as I'm still learning to manage everything in Github. I'm open to any ideas to improve this integration and would greatly appreciate any help with identifying and fixing issues.

---

### Home Assistant Card for this Integration:

 [Energy and Power Monitor Card](https://github.com/KrX3D/Energy-and-Power-Monitor-Card).

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

- You can build a hierarchical view, where the topmost entity aggregates all the values from sub-entities:

                                                HOUSE
                    "Living Room"               "Kitchen"                   "Bathroom"  ...
            "Plug Window" "Plug Table"      "Device 1" "Device 2"             "Fan"     ...


This way, you can monitor which device or room consumes how much energy or power.

---

### Current Issues (Known Bugs)

Here are some known problems that I am currently working on fixing, and some i currently don't know hot to solve:

1. **Add/Reconfigure GUI:**
 - In the Smart Meter Device dropdown, you can hit the 'X' and the dropdown will be empty, it would be nice if it selects None when doing that. Fixed it so that if empty None is selected when adding a room.
 - How can I update the entities in one dropdown box when an entity is selected in a second dropdown box (e.g., Smart Meter Device and Entity dropdowns)?
 
2. **Sensor Update Interval:**
 - The update interval for all sensors needs better handling.
   
3. **Sensor removed in Home Assistant:**
 - If a sensor was removed or renamed in Home Assistant, also remove it in this integration if it was selected, currently it is removed and the integration works but you need to manually open the room and hit ok to save it again or else a message will apways pop um in the logs

---

### Upcoming Features

I'm also working on a custom card for this integration. I'll post the link here once it's ready.

