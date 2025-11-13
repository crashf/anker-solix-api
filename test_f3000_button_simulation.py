#!/usr/bin/env python3
"""F3000 Button Press Simulation - Alternative AC Control Approach"""

import asyncio
import time
from aiohttp import ClientSession

import common
from api import api
from api.mqtttypes import DeviceHexData, DeviceHexDataHeader, DeviceHexDataField, DeviceHexDataTypes

# Setup logging
CONSOLE = common.CONSOLE

async def test_button_press_simulation():
    """Test AC control by simulating button press commands."""
    CONSOLE.info("F3000 Button Press Simulation")
    CONSOLE.info("=" * 40)
    
    user = common.user()
    password = common.password()
    country = common.country()
    
    async with ClientSession() as websession:
        myapi = api.AnkerSolixApi(
            email=user,
            password=password,
            countryId=country,
            websession=websession,
            logger=CONSOLE
        )
        
        await myapi.update_sites()
        await myapi.update_device_details()
        
        f3000_devices = [
            dev for dev in myapi.devices.values() 
            if dev.get('device_pn') == 'A1782'
        ]
        
        if not f3000_devices:
            CONSOLE.error("No F3000 found!")
            return
        
        device_dict = f3000_devices[0]
        device_sn = device_dict.get('device_sn')
        CONSOLE.info(f"Found F3000: {device_sn}")
        
        if not await myapi.startMqttSession():
            CONSOLE.error("Failed to start MQTT")
            return
        
        mqtt = myapi.mqttsession
        CONSOLE.info("MQTT connected")
        
        # Try different control message types
        control_tests = [
            # Try message type 0103 (reverse of what we're seeing)
            ("0103", "AC Button Press - Type 1"),
            
            # Try common control message types
            ("0001", "Generic Control - Type 1"),
            ("0002", "Generic Control - Type 2"), 
            ("0005", "Generic Control - Type 5"),
            ("0010", "System Control"),
            ("0020", "Power Control"),
            ("0050", "Device Control"),
            
            # Try F3000-specific guesses
            ("3001", "F3000 Control - Type 1"),
            ("3005", "F3000 Control - Type 5"),
        ]
        
        for msg_type, description in control_tests:
            CONSOLE.info(f"\nTesting {msg_type}: {description}")
            
            try:
                # Create command
                hexdata = DeviceHexData(msg_header=DeviceHexDataHeader(cmd_msg=msg_type))
                
                # Try minimal fields - just a button press indicator
                hexdata.update_field(DeviceHexDataField(hexbytes="a10101"))  # Button ID
                hexdata.update_field(DeviceHexDataField(hexbytes="a2010101")) # Action (press)
                hexdata.add_timestamp_field()
                
                hex_data = hexdata.hexbytes.hex()
                CONSOLE.info(f"  Command: {hex_data}")
                
                result = mqtt.publish(
                    deviceDict=device_dict,
                    hexbytes=hex_data
                )
                
                result_code = result[1].rc if len(result) > 1 else 'unknown'
                CONSOLE.info(f"  Result: {result_code}")
                
                # Wait and see if anything happens
                await asyncio.sleep(3)
                
                # Ask user if they saw any change
                response = input("  Any change in AC output? (y/n/q): ").lower()
                if response == 'y':
                    CONSOLE.info(f"🎉 SUCCESS with message type {msg_type}!")
                    return msg_type
                elif response == 'q':
                    break
                    
            except Exception as e:
                CONSOLE.error(f"  Error: {e}")
        
        CONSOLE.info("\n🤔 No button press simulation worked")
        
        # Final attempt - try the Anker Power app's actual button commands
        CONSOLE.info("\nFinal test: Anker app simulation")
        CONSOLE.info("This tries to replicate what the Anker Power app sends...")
        
        # These are educated guesses based on common Anker device patterns
        app_commands = [
            "ff09120003000f0030a1010ca2010101fe05031234abcd",  # App-style AC toggle
            "ff09150003000f0050a1010ca2010101a3010101fe05031234abcd",  # Extended app command
        ]
        
        for i, cmd in enumerate(app_commands):
            CONSOLE.info(f"\nApp Command {i+1}")
            try:
                # Update timestamp
                timestamp = int(time.time())
                cmd_with_timestamp = cmd[:-16] + f"{timestamp & 0xFFFFFFFF:08x}" + cmd[-8:]
                
                result = mqtt.publish(
                    deviceDict=device_dict,
                    hexbytes=cmd_with_timestamp
                )
                
                CONSOLE.info(f"  Result: {result[1].rc if len(result) > 1 else 'unknown'}")
                await asyncio.sleep(3)
                
                response = input("  Any AC output change? (y/n): ").lower()
                if response == 'y':
                    CONSOLE.info(f"🎉 SUCCESS with app command {i+1}!")
                    return f"app_cmd_{i+1}"
                    
            except Exception as e:
                CONSOLE.error(f"  Error: {e}")
        
        CONSOLE.info("\n📝 Test completed - no working commands found")
        CONSOLE.info("The F3000 may require a different control approach.")

if __name__ == "__main__":
    asyncio.run(test_button_press_simulation())