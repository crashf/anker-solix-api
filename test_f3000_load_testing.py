#!/usr/bin/env python3
"""F3000 Load Testing - Real-time AC Control with Power Monitoring"""

import asyncio
import json
import time
from aiohttp import ClientSession

import common
from api import api

# Setup logging
CONSOLE = common.CONSOLE

class F3000LoadTester:
    """Test F3000 AC control with real-time power monitoring."""
    
    def __init__(self):
        self.api = None
        self.mqtt = None
        self.device_dict = None
        self.power_readings = []
        self.monitoring = True
        
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
            
            await self.api.update_sites()
            await self.api.update_device_details()
            
            f3000_devices = [
                dev for dev in self.api.devices.values() 
                if dev.get('device_pn') == 'A1782'
            ]
            
            if not f3000_devices:
                CONSOLE.error("No F3000 found!")
                return False
                
            self.device_dict = f3000_devices[0]
            device_sn = self.device_dict.get('device_sn')
            CONSOLE.info(f"Found F3000: {device_sn}")
            
            if await self.api.startMqttSession():
                self.mqtt = self.api.mqttsession
                CONSOLE.info("MQTT connected")
                return True
            else:
                CONSOLE.error("Failed to connect MQTT")
                return False
    
    def parse_mqtt_power_data(self, payload_data):
        """Parse MQTT payload to extract power readings."""
        try:
            import base64
            
            # Decode the base64 payload
            decoded = base64.b64decode(payload_data)
            hex_data = decoded.hex()
            
            # Look for power consumption patterns based on our field mappings
            # This is a simplified parser - you could enhance it
            power_info = {
                'hex': hex_data,
                'timestamp': time.time(),
                'ac_power': 'Unknown',
                'usb_power': 'Unknown',
                'message_type': 'Unknown'
            }
            
            # Try to extract message type
            if len(decoded) >= 9:
                msg_type = decoded[7:9].hex()
                power_info['message_type'] = msg_type
                
                # Parse fields for known message types
                if msg_type in ['0421', '0401']:  # Our power monitoring messages
                    # This is where you'd parse the actual power fields
                    # Based on our field mappings: a3 = power_consumption
                    power_info['parsed'] = 'AC power message detected'
            
            return power_info
            
        except Exception as e:
            return {'error': f'Parse error: {e}', 'raw': str(payload_data)}
    
    async def power_monitor(self):
        """Monitor power readings continuously."""
        def message_callback(client, userdata, message):
            """Process MQTT messages for power monitoring."""
            try:
                topic = message.topic
                payload = json.loads(message.payload.decode())
                
                if 'payload' in payload:
                    # Parse the power data
                    power_data = self.parse_mqtt_power_data(payload['payload'])
                    self.power_readings.append(power_data)
                    
                    # Display real-time power info
                    timestamp = time.strftime('%H:%M:%S')
                    msg_type = power_data.get('message_type', 'Unknown')
                    
                    print(f"\r[{timestamp}] MSG: {msg_type} | Raw: {power_data.get('hex', '')[:20]}...    ", end='', flush=True)
                
            except Exception as e:
                pass  # Ignore parsing errors during monitoring
        
        # Set up monitoring
        self.mqtt.client.on_message = message_callback
        
        device_sn = self.device_dict.get('device_sn')
        topics = [
            f"dt/anker_power/A1782/{device_sn}/state_info",
            f"dt/anker_power/A1782/{device_sn}/param_info",
            f"cmd/anker_power/A1782/{device_sn}/res"
        ]
        
        for topic in topics:
            self.mqtt.subscribe(topic)
        
        CONSOLE.info(f"🔍 Power monitoring started - watching {len(topics)} topics")
        
        # Monitor until stopped
        while self.monitoring:
            await asyncio.sleep(0.5)
    
    async def send_ac_command(self, enable: bool, command_type: str = "0057"):
        """Send AC control command with specified type."""
        try:
            timestamp_str = time.strftime('%H:%M:%S')
            action = "🟢 ENABLE" if enable else "🔴 DISABLE"
            
            print(f"\n[{timestamp_str}] {action} AC OUTPUT (Type: {command_type})")
            
            # Use the realtime trigger as our baseline
            if command_type == "trigger":
                result = self.mqtt.realtime_trigger(
                    deviceDict=self.device_dict,
                    timeout=300
                )
                print(f"  → Trigger sent: {result}")
                
            else:
                # Send raw hex command based on type
                commands = {
                    "0057_disable": "ff091e0003000f0057a10122a2020100a305033c000000fe0503dd231669",
                    "0057_enable": "ff091e0003000f0057a10122a2020102a305033c000000fe0503dd231669",
                    "0401_disable": "ff09140003000f0104a10100a2010100fe0503dd231669",
                    "0401_enable": "ff09140003000f0104a10100a2010101fe0503dd231669",
                    "0421_disable": "ff09140003000f2104a10100a2010100fe0503dd231669", 
                    "0421_enable": "ff09140003000f2104a10100a2010101fe0503dd231669",
                }
                
                cmd_key = f"{command_type}_{'enable' if enable else 'disable'}"
                if cmd_key in commands:
                    # Update timestamp in hex command
                    cmd_hex = commands[cmd_key]
                    timestamp = int(time.time())
                    cmd_with_timestamp = cmd_hex[:-16] + f"{timestamp & 0xFFFFFFFF:08x}" + cmd_hex[-8:]
                    
                    result = self.mqtt.publish(
                        deviceDict=self.device_dict,
                        hexbytes=cmd_with_timestamp
                    )
                    
                    result_code = result[1].rc if len(result) > 1 else 'unknown'
                    print(f"  → Command sent: {result_code}")
                else:
                    print(f"  → Unknown command type: {cmd_key}")
            
            await asyncio.sleep(1)
            return True
            
        except Exception as e:
            print(f"  → Error: {e}")
            return False

async def main():
    """Main load testing function."""
    print("🔋 F3000 Load Testing - Real-time AC Control Monitor")
    print("=" * 65)
    print()
    print("📋 SETUP INSTRUCTIONS:")
    print("1. Connect a small load to F3000 AC outlet (lamp, phone charger)")
    print("2. Note the current state of your load device")
    print("3. Watch the real-time monitoring output")
    print("4. Observe if load device turns on/off with commands")
    print()
    
    input("Press Enter when load is connected and ready...")
    
    tester = F3000LoadTester()
    
    try:
        if not await tester.connect():
            return
        
        # Start power monitoring in background
        monitor_task = asyncio.create_task(tester.power_monitor())
        await asyncio.sleep(2)  # Let monitoring stabilize
        
        print("\n🎯 TESTING SEQUENCE:")
        print("=" * 50)
        
        # Test sequence with different command types
        test_sequence = [
            ("trigger", None, "Baseline trigger command"),
            ("0057", False, "Update trigger - DISABLE"),
            ("0057", True, "Update trigger - ENABLE"),
            ("0401", False, "Direct 0401 - DISABLE"),
            ("0401", True, "Direct 0401 - ENABLE"),
            ("0421", False, "Direct 0421 - DISABLE"), 
            ("0421", True, "Direct 0421 - ENABLE"),
        ]
        
        for i, (cmd_type, enable, description) in enumerate(test_sequence):
            print(f"\n📍 Test {i+1}: {description}")
            
            if cmd_type == "trigger":
                await tester.send_ac_command(True, "trigger")
            else:
                await tester.send_ac_command(enable, cmd_type)
            
            # Wait and ask user to observe
            print("   ⏳ Waiting 5 seconds - OBSERVE YOUR LOAD DEVICE...")
            for j in range(5):
                print(f"   {5-j}...", end=' ', flush=True)
                await asyncio.sleep(1)
            print("✓")
            
            # Ask user for feedback
            if i < len(test_sequence) - 1:  # Don't ask after last test
                response = input("   Did you see any change in your load device? (y/n/q): ").lower()
                if response == 'q':
                    break
                elif response == 'y':
                    print(f"   🎉 SUCCESS! Command {cmd_type} {'enable' if enable else 'disable'} worked!")
                    # Continue with remaining tests
                    continue_test = input("   Continue testing other commands? (y/n): ").lower()
                    if continue_test != 'y':
                        break
        
        print("\n🏁 Testing completed!")
        print("\n📊 Power readings collected:", len(tester.power_readings))
        
        # Stop monitoring
        tester.monitoring = False
        await asyncio.sleep(1)
        
        # Show summary
        print("\n📈 MONITORING SUMMARY:")
        if tester.power_readings:
            print(f"   Total messages: {len(tester.power_readings)}")
            message_types = {}
            for reading in tester.power_readings:
                msg_type = reading.get('message_type', 'Unknown')
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
            
            for msg_type, count in message_types.items():
                print(f"   {msg_type}: {count} messages")
        else:
            print("   No power readings captured")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted")
        tester.monitoring = False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        tester.monitoring = False
    finally:
        print("\nTest completed - check your load device status!")

if __name__ == "__main__":
    asyncio.run(main())