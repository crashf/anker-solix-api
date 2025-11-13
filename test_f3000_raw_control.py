#!/usr/bin/env python3
"""F3000 Simple AC Control Test - Raw Command Approach"""

import asyncio
import json
import time
from aiohttp import ClientSession

import common
from api import api

# Setup logging
CONSOLE = common.CONSOLE

async def test_raw_ac_control():
    """Test AC control by sending raw hex commands directly."""
    CONSOLE.info("F3000 Raw AC Control Test")
    CONSOLE.info("=" * 40)
    
    # Get credentials
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
        
        # Connect and find device
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
        
        # Connect to MQTT
        if not await myapi.startMqttSession():
            CONSOLE.error("Failed to start MQTT session")
            return
        
        mqtt = myapi.mqttsession
        CONSOLE.info("MQTT connected")
        
        # Subscribe to monitor responses
        def message_callback(client, userdata, message):
            try:
                topic = message.topic
                payload = json.loads(message.payload.decode())
                CONSOLE.info(f"Response: {topic}")
                CONSOLE.info(f"Data: {payload.get('payload', 'No payload')}")
            except:
                pass
        
        mqtt.client.on_message = message_callback
        
        # Subscribe to all device topics
        topics = [
            f"dt/anker_power/A1782/{device_sn}/state_info",
            f"dt/anker_power/A1782/{device_sn}/param_info", 
            f"cmd/anker_power/A1782/{device_sn}/res"
        ]
        
        for topic in topics:
            mqtt.subscribe(topic)
            
        CONSOLE.info("Subscribed to device topics")
        
        # Test different raw hex commands
        test_commands = [
            # Based on working update trigger, try minimal changes
            "ff091e0003000f0057a10122a2020100a305033c000000fe0503dd231669",  # Original with 00
            "ff091e0003000f0057a10122a2020101a305033c000000fe0503dd231669",  # Original with 01
            "ff091e0003000f0057a10122a2020102a305033c000000fe0503dd231669",  # Original with 02
            
            # Try message type 0401 (simple version)
            "ff09140003000f0104a10100a2010100fe0503dd231669",  # 0401 disable
            "ff09140003000f0104a10100a2010101fe0503dd231669",  # 0401 enable
            
            # Try message type 0421 (simple version)  
            "ff09140003000f2104a10100a2010100fe0503dd231669",  # 0421 disable
            "ff09140003000f2104a10100a2010101fe0503dd231669",  # 0421 enable
        ]
        
        for i, cmd in enumerate(test_commands):
            CONSOLE.info(f"\nTest {i+1}: {cmd[:20]}...{cmd[-10:]}")
            
            try:
                # Update timestamp in command (last 8 chars before checksum)
                timestamp = int(time.time())
                # Replace the timestamp bytes in the hex string
                cmd_with_timestamp = cmd[:-16] + f"{timestamp & 0xFFFFFFFF:08x}" + cmd[-8:]
                
                result = mqtt.publish(
                    deviceDict=device_dict,
                    hexbytes=cmd_with_timestamp
                )
                
                CONSOLE.info(f"Sent: {result[1].rc if len(result) > 1 else 'ok'}")
                await asyncio.sleep(3)  # Wait to see response
                
            except Exception as e:
                CONSOLE.error(f"Error: {e}")
                
        CONSOLE.info("\nTest completed. Check AC output status!")

if __name__ == "__main__":
    asyncio.run(test_raw_ac_control())