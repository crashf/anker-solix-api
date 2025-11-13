#!/usr/bin/env python3
"""Test script for F3000 MQTT Control Commands.

This script tests MQTT control capabilities for the Anker SOLIX F3000 (A1782).
Based on successful power monitoring field discoveries.

WARNING: This is experimental! Test carefully on your device.
"""

import asyncio
import json
import logging
from datetime import datetime

from aiohttp import ClientSession
from api import api
from api.errors import AnkerSolixError
import common

# Configure logging
CONSOLE: logging.Logger = common.CONSOLE
CONSOLE.name = "F3000Control"
CONSOLE.handlers[0].setLevel(logging.INFO)

class F3000ControlTester:
    """Test MQTT control commands for F3000."""
    
    def __init__(self):
        self.api = None
        self.mqtt = None
        self.device_dict = None
        
    async def connect(self):
        """Connect to API and MQTT."""
        user = common.user()
        password = common.password()
        country = common.country()
        
        async with ClientSession() as websession:
            self.api = api.AnkerSolixApi(
                email=user,
                password=password, 
                countryId=country,
                websession=websession,
                logger=CONSOLE
            )
            
            # Authenticate and get devices
            await self.api.update_sites()
            await self.api.update_device_details()
            
            # Find F3000 device
            f3000_devices = [
                dev for dev in self.api.devices.values() 
                if dev.get('device_pn') == 'A1782'
            ]
            
            if not f3000_devices:
                CONSOLE.error("No F3000 (A1782) device found!")
                return False
                
            self.device_dict = f3000_devices[0]
            CONSOLE.info(f"Found F3000: {self.device_dict.get('device_sn', 'Unknown SN')}")
            
            # Connect to MQTT
            if await self.api.startMqttSession():
                self.mqtt = self.api.mqttsession
                CONSOLE.info(f"MQTT connection established: {self.mqtt.client.is_connected() if self.mqtt.client else 'No client'}")
                return True
            else:
                CONSOLE.error("Failed to establish MQTT connection")
                return False
    
    async def test_ac_control(self, enable: bool = True):
        """Test AC output control command."""
        CONSOLE.info(f"Testing AC output control: {'ENABLE' if enable else 'DISABLE'}")
        
        try:
            # Let's try a different approach - modify the update trigger command
            # by manually crafting the hex data based on the working format
            
            # The working update trigger hex was:
            # ff091e0003000f0057a10122a2020101a305033c000000fe0503dd231669
            # Let's try changing the a2 field value to control AC output
            
            # Create the base command with our AC control modification
            from api.mqtttypes import DeviceHexData, DeviceHexDataHeader, DeviceHexDataField, DeviceHexDataTypes
            import time
            
            # Use the same message structure as update_trigger (0057) but modify the a2 field
            hexdata = DeviceHexData(msg_header=DeviceHexDataHeader(cmd_msg="0057"))
            
            # a1 field - keep same as update trigger
            hexdata.update_field(DeviceHexDataField(hexbytes="a10122"))
            
            # a2 field - try to modify for AC control instead of just update toggle
            # Original was a2020101, let's try different values
            if enable:
                # Try value 1 for enable
                hexdata.update_field(DeviceHexDataField(hexbytes="a2020102"))  # Change last byte to 02
            else:
                # Try value 0 for disable  
                hexdata.update_field(DeviceHexDataField(hexbytes="a2020100"))  # Change last byte to 00
            
            # a3 field - timeout (keep same)
            hexdata.update_field(
                DeviceHexDataField(
                    f_name=bytes.fromhex("a3"),
                    f_type=DeviceHexDataTypes.var.value,
                    f_value=int(60).to_bytes(4, byteorder="little")
                )
            )
            
            # Add timestamp
            hexdata.add_timestamp_field()
            
            hex_data = hexdata.hexbytes.hex()
            CONSOLE.info(f"Generated AC control hex: {hex_data}")
            
            # Publish the command  
            result = self.mqtt.publish(
                deviceDict=self.device_dict,
                hexbytes=hex_data
            )
            
            CONSOLE.info(f"Publish result: {result}")
            
            # Wait for response
            await asyncio.sleep(3)
            return True
                
        except Exception as e:
            CONSOLE.error(f"Error testing AC control: {e}")
            return False

    async def test_data_trigger(self):
        """Test real-time data trigger command."""
        CONSOLE.info("Testing real-time data trigger...")
        
        try:
            # Use the built-in realtime trigger method
            result = self.mqtt.realtime_trigger(
                deviceDict=self.device_dict,
                timeout=300  # 5 minutes
            )
            
            CONSOLE.info(f"Trigger sent: {result}")
            await asyncio.sleep(2)
            return True
                
        except Exception as e:
            CONSOLE.error(f"Error testing data trigger: {e}")
            return False
    
    async def monitor_responses(self, duration: int = 30):
        """Monitor MQTT responses for a specified duration."""
        CONSOLE.info(f"Monitoring MQTT responses for {duration} seconds...")
        
        def message_callback(client, userdata, message):
            """Callback for MQTT messages."""
            try:
                topic = message.topic
                payload = json.loads(message.payload.decode())
                CONSOLE.info(f"Received on {topic}:")
                CONSOLE.info(f"  Payload: {json.dumps(payload, indent=2)}")
            except Exception as e:
                CONSOLE.error(f"Error processing message: {e}")
        
        # Set up message callback
        if self.mqtt and self.mqtt.client:
            self.mqtt.client.on_message = message_callback
            
            # Subscribe to device topics
            device_sn = self.device_dict.get('device_sn')
            topics = [
                f"dt/anker_power/A1782/{device_sn}/state_info",
                f"dt/anker_power/A1782/{device_sn}/param_info",
                f"cmd/anker_power/A1782/{device_sn}/res"  # Response topic
            ]
            
            for topic in topics:
                self.mqtt.subscribe(topic)
                CONSOLE.info(f"Subscribed to: {topic}")
        
        # Monitor for specified duration
        await asyncio.sleep(duration)

async def main():
    """Main test function."""
    CONSOLE.info("F3000 MQTT Control Testing")
    CONSOLE.info("=" * 50)
    
    tester = F3000ControlTester()
    
    try:
        # Connect to API and MQTT
        if not await tester.connect():
            return
        
        # Start monitoring
        monitor_task = asyncio.create_task(tester.monitor_responses(60))
        
        # Test data trigger first (safest)
        CONSOLE.info("\n1. Testing real-time data trigger...")
        await tester.test_data_trigger()
        await asyncio.sleep(5)
        
        # Test AC control (more experimental)
        CONSOLE.info("\n2. Testing AC output control...")
        CONSOLE.info("Auto-testing AC control with modified commands...")
        
        # Try to toggle AC output
        await tester.test_ac_control(enable=False)  # Turn off first
        await asyncio.sleep(5)
        await tester.test_ac_control(enable=True)   # Turn back on
        
        # Wait for monitoring to complete
        await monitor_task
        
    except KeyboardInterrupt:
        CONSOLE.info("Test interrupted by user")
    except Exception as e:
        CONSOLE.error(f"Test error: {e}")
    finally:
        CONSOLE.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main())