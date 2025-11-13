#!/usr/bin/env python3
"""F3000 AC Control Test - Targeted Message Types"""

import asyncio
import json
import time
from aiohttp import ClientSession

import common
from api import api
from api.mqtttypes import DeviceHexData, DeviceHexDataHeader, DeviceHexDataField, DeviceHexDataTypes

# Setup logging
CONSOLE = common.CONSOLE

class F3000ACControlTester:
    """Test AC control using the correct message types (0401/0421)."""
    
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
                CONSOLE.info(f"MQTT connection established")
                return True
            else:
                CONSOLE.error("Failed to establish MQTT connection")
                return False

    async def test_message_type_0401(self, enable: bool):
        """Test AC control using message type 0401."""
        CONSOLE.info(f"Testing 0401 message type - AC {'ENABLE' if enable else 'DISABLE'}")
        
        try:
            # Create command for message type 0401
            hexdata = DeviceHexData(msg_header=DeviceHexDataHeader(cmd_msg="0104"))  # 0401 in little endian
            
            # a1 - status code
            hexdata.update_field(DeviceHexDataField(hexbytes="a10100"))
            
            # a2 - AC output control (the key field!)
            ac_value = 1 if enable else 0
            hexdata.update_field(DeviceHexDataField(hexbytes=f"a20101{ac_value:02x}"))
            
            # a3 - power consumption (set to 0 for control command)
            hexdata.update_field(DeviceHexDataField(hexbytes="a3050300000000"))
            
            # Add timestamp
            hexdata.add_timestamp_field()
            
            hex_data = hexdata.hexbytes.hex()
            CONSOLE.info(f"Generated 0401 command: {hex_data}")
            
            # Publish command
            result = self.mqtt.publish(
                deviceDict=self.device_dict,
                hexbytes=hex_data
            )
            
            CONSOLE.info(f"0401 command result: {result[1].rc if len(result) > 1 else result}")
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            CONSOLE.error(f"Error with 0401 command: {e}")
            return False
    
    async def test_message_type_0421(self, enable: bool):
        """Test AC control using message type 0421."""
        CONSOLE.info(f"Testing 0421 message type - AC {'ENABLE' if enable else 'DISABLE'}")
        
        try:
            # Create command for message type 0421  
            hexdata = DeviceHexData(msg_header=DeviceHexDataHeader(cmd_msg="2104"))  # 0421 in little endian
            
            # a1 - status code
            hexdata.update_field(DeviceHexDataField(hexbytes="a10100"))
            
            # a2 - AC output control 
            ac_value = 1 if enable else 0
            hexdata.update_field(DeviceHexDataField(hexbytes=f"a20101{ac_value:02x}"))
            
            # Add timestamp
            hexdata.add_timestamp_field()
            
            hex_data = hexdata.hexbytes.hex()
            CONSOLE.info(f"Generated 0421 command: {hex_data}")
            
            # Publish command
            result = self.mqtt.publish(
                deviceDict=self.device_dict,
                hexbytes=hex_data
            )
            
            CONSOLE.info(f"0421 command result: {result[1].rc if len(result) > 1 else result}")
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            CONSOLE.error(f"Error with 0421 command: {e}")
            return False
    
    async def test_different_field_values(self):
        """Test different values in the a2 field."""
        CONSOLE.info("Testing different a2 field values...")
        
        test_values = [0x00, 0x01, 0x02, 0x03, 0xFF]
        
        for value in test_values:
            CONSOLE.info(f"Testing a2 value: {value:02x}")
            
            try:
                # Use 0401 message type for this test
                hexdata = DeviceHexData(msg_header=DeviceHexDataHeader(cmd_msg="0104"))
                hexdata.update_field(DeviceHexDataField(hexbytes="a10100"))
                hexdata.update_field(DeviceHexDataField(hexbytes=f"a20101{value:02x}"))
                hexdata.add_timestamp_field()
                
                hex_data = hexdata.hexbytes.hex()
                result = self.mqtt.publish(
                    deviceDict=self.device_dict,
                    hexbytes=hex_data
                )
                
                CONSOLE.info(f"Value {value:02x} result: {result[1].rc if len(result) > 1 else 'sent'}")
                await asyncio.sleep(3)  # Wait longer to observe changes
                
            except Exception as e:
                CONSOLE.error(f"Error testing value {value:02x}: {e}")
    
    async def monitor_responses(self, duration: int = 30):
        """Monitor MQTT responses."""
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
                f"cmd/anker_power/A1782/{device_sn}/res"
            ]
            
            for topic in topics:
                self.mqtt.subscribe(topic)
                CONSOLE.info(f"Subscribed to: {topic}")
        
        await asyncio.sleep(duration)

async def main():
    """Main test function."""
    CONSOLE.info("F3000 AC Control - Targeted Message Types")
    CONSOLE.info("=" * 60)
    
    tester = F3000ACControlTester()
    
    try:
        if not await tester.connect():
            return
        
        # Start monitoring
        monitor_task = asyncio.create_task(tester.monitor_responses(60))
        
        CONSOLE.info("\n1. Testing message type 0401 (where AC control field was found)")
        await tester.test_message_type_0401(False)  # Disable
        await asyncio.sleep(3)
        await tester.test_message_type_0401(True)   # Enable
        await asyncio.sleep(3)
        
        CONSOLE.info("\n2. Testing message type 0421 (alternative AC control)")
        await tester.test_message_type_0421(False)  # Disable  
        await asyncio.sleep(3)
        await tester.test_message_type_0421(True)   # Enable
        await asyncio.sleep(3)
        
        CONSOLE.info("\n3. Testing different field values")
        await tester.test_different_field_values()
        
        # Wait for monitoring to complete
        await monitor_task
        
    except KeyboardInterrupt:
        CONSOLE.info("Test interrupted")
    except Exception as e:
        CONSOLE.error(f"Test error: {e}")
    finally:
        CONSOLE.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main())