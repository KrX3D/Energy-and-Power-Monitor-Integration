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
