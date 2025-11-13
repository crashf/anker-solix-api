#!/usr/bin/env python3
"""
F3000 MQTT Power Monitor
Shows real-time AC power from MQTT data (the reliable method)
"""

import asyncio
import struct
from datetime import datetime
import logging

from aiohttp import ClientSession
from api.api import AnkerSolixApi
from api.mqtt import AnkerSolixMqttSession
from common import user, password, country

def decode_power_from_hex(hex_data):
    """Extract AC power from hex data like we saw in the MQTT monitor"""
    try:
        # Look for patterns like 6d:02 (621W), 69:02 (617W), 67:02 (615W)
        # These appear at specific positions in the 0421 message type
        
        # Convert hex string to bytes
        if isinstance(hex_data, str):
            # Remove colons and convert to bytes
            clean_hex = hex_data.replace(':', '')
            data_bytes = bytes.fromhex(clean_hex)
        else:
            data_bytes = hex_data
            
        # Look for power consumption pattern
        # In 0421 messages, field a6 contains USB power data where we saw the AC power
        # Pattern: a6:0a:04:XX:XX:00:00:00:00:YY:YY:5a
        # Where XX:XX is the power value in little endian
        
        for i in range(len(data_bytes) - 10):
            # Look for a6 field marker
            if data_bytes[i] == 0xa6 and i + 10 < len(data_bytes):
                # Extract power value (little endian)
                if data_bytes[i+1] == 0x0a and data_bytes[i+2] == 0x04:
                    power_bytes = data_bytes[i+3:i+5]
                    if len(power_bytes) >= 2:
                        power = struct.unpack('<H', power_bytes)[0]  # Little endian 16-bit
                        if 0 < power < 4000:  # Reasonable power range
                            return power
                            
        return None
    except Exception:
        return None

async def monitor_f3000_mqtt():
    """Monitor F3000 using MQTT for real-time power data"""
    
    print("🔋 F3000 MQTT Power Monitor")
    print("=" * 40)
    print("Connecting to your F3000...")
    
    # Suppress verbose logging
    logging.getLogger().setLevel(logging.WARNING)
    
    async with ClientSession() as websession:
        try:
            # Initialize API
            myapi = AnkerSolixApi(
                email=user(),
                password=password(),
                countryId=country(),
                websession=websession,
                logger=logging.getLogger(__name__)
            )
            
            # Get device info
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000
            f3000_sn = None
            for sn, device in myapi.devices.items():
                if device.get('device_pn') == 'A1782':
                    f3000_sn = sn
                    alias = device.get('alias', 'F3000')
                    break
            
            if not f3000_sn:
                print("❌ F3000 device not found!")
                return
                
            print(f"✅ Found: {alias} ({f3000_sn})")
            print("🔌 Connecting to MQTT for real-time power data...")
            print("=" * 50)
            print("Press Ctrl+C to stop")
            print()
            
            # Start MQTT session using the API method
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ Failed to start MQTT session")
                return
                
            last_power = None
            
            def message_callback(client, userdata, topic, payload, qos, properties, response_topic, correlation_data):
                nonlocal last_power
                
                try:
                    # Parse MQTT message
                    topic_str = topic.decode() if isinstance(topic, bytes) else str(topic)
                    
                    # Only process messages for our F3000
                    if f3000_sn not in topic_str:
                        return
                        
                    # Parse the payload
                    import json
                    message_data = json.loads(payload.decode())
                    
                    # Extract hex data
                    hex_data = message_data.get('payload', {}).get('data')
                    if not hex_data:
                        return
                        
                    # Decode base64 to hex
                    import base64
                    try:
                        decoded_bytes = base64.b64decode(hex_data)
                        
                        # Convert to hex string for our decoder
                        hex_string = ':'.join([f'{b:02x}' for b in decoded_bytes])
                        
                        # Extract power
                        power = decode_power_from_hex(decoded_bytes)
                        
                        if power is not None and power != last_power:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            
                            if power == 0:
                                status = "🔴 OFF"
                            elif power < 50:
                                status = "🟡 LOW"
                            else:
                                status = "🟢 ACTIVE"
                            
                            print(f"[{timestamp}] AC Power: {power:4d}W  {status}")
                            last_power = power
                            
                    except Exception:
                        pass
                        
                except Exception:
                    pass
            
            # Set up MQTT connection and callback
            mqtt_session.set_message_callback(message_callback)
            
            # Subscribe to device topic using the session's method
            topic_prefix = mqtt_session.get_topic_prefix(deviceDict={'device_sn': f3000_sn, 'device_pn': 'A1782'})
            if topic_prefix:
                await mqtt_session.subscribe([f"{topic_prefix}/#"])
            else:
                # Fallback to direct topic
                topic = f"dt/anker_power/A1782/{f3000_sn}/#"
                await mqtt_session.subscribe([topic])
            
            print("⏳ Waiting for MQTT messages...")
            print("   (Turn your F3000 AC on/off to see power changes)")
            print()
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure your F3000 is online")

if __name__ == "__main__":
    try:
        asyncio.run(monitor_f3000_mqtt())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")