# Energy-and-Power-Monitor-Integration
A Home Assistant Integration to group energy and power sensors for rooms or smart power monitor devices, and get the values of the grouped entities and also the not tracked power

############################

UNDER DEVELOPMENT - STILL TESTING

############################

Hello, this is my first integration and my first reposity which i opened myself. Im still prety "new" to managing github, so bear with me.

Im greatfull for ideas to improve this integration and pointing/fixing some problems.

############################

What is this integration: (will be updated soon with more infos)

- in th is integration you can create several groups for your energy and power sensors
- most of the dropdown boxes get filtered, so if you added an energy/power sensor to one integration entity it wont show up for selection anymore until it gets unselected
- on the first gui you can select between energy and power which will filter the entities on the second gui
- Second gui:
    -Entities:
        - Select the energy/power entities for i.e the Living Room
        - A sensor will be created with all energy/power values combined i.e. "Selected entities - Power"
    - Smart Monitor Device 
        Select an Smart Meter for that room (Living Room), you can also leave it to None. The value of the selected Smart Meter will be used to and the selected entities for that room will be subtracted. The difference will be put into a second sensor i.e. "Untracked - Power"
    - If you have more Rooms/Subrooms created they will be shown under Created Rooms.
        - Selecting the room will add the value of i.e. "Selected entities - Power" and if present i.e. "Untracked - Power" to this room

- So you can create something like a tree "view", where the topmost can have all the values combined

                                                HOUSE
                "Living Room"               "Kitchen"                   "Bath"  ......
        "Plug Window" "Plug Table"      "Device 1" "Device 2"           "Fan"   ......

- Like this you can see which device/room consumes how much energy/power


############################

So far it seems to work for me, the only known problems that i dont understand how to fix them right now are:

- Add/reconfig gui -> Smart Monitor Device dropdown -> howto remove the X or set the default to None when clicking X (showing it in the gui) 
- Add/reconfig gui -> update the entities from one dropdown box when selecting an entity in a second dropdown box (Smart Monitor Device - Entity dropdowns)
- Add -> created an entry with i.e. "Power - XXXX" but when clicking on reconfig the title ist updated again to this schema -> config_flow.py line 407 -> title=f"{translated_entity_type} - {self.options[CONF_ROOM]}",
- Reconfig gui -> renaming an option -> also updating/deleting the new sensor name in all the other options -> sensor attribute "selected_entities" and "Energy and Power Monitor"
- only German and English translation are tested, all other translation where created by ChatGPT, so hopefully they are good
- update intervall of all sensors needs to be better handled

im currently also working on a custom card and i post the link here when its finished.