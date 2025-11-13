#!/usr/bin/env python3
"""
F3000 Live AC Power Monitor
Shows real-time AC power consumption from your F3000 device via MQTT
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

from aiohttp import ClientSession
from api.api import AnkerSolixApi
from common import user, password, country

# Disable verbose logging
logging.getLogger().setLevel(logging.ERROR)

async def monitor_f3000_power():
    """Monitor F3000 AC power consumption in real-time"""
    
    print("🔋 F3000 Live AC Power Monitor")
    print("=" * 40)
    print("Connecting to your F3000 device...")
    
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
            
            # Find F3000 device
            f3000_device = None
            for device_sn, device_info in myapi.devices.items():
                if device_info.get('device_pn') == 'A1782':
                    f3000_device = device_info
                    break
            
            if not f3000_device:
                print("❌ F3000 device not found!")
                return
                
            device_sn = f3000_device['device_sn']
            alias = f3000_device.get('alias', 'F3000')
            
            print(f"✅ Connected to: {alias} ({device_sn})")
            print(f"📍 Location: {f3000_device.get('site_name', 'Unknown')}")
            print()
            print("🔌 Live AC Power Consumption:")
            print("=" * 40)
            print("Press Ctrl+C to stop monitoring")
            print()
            
            # Start MQTT monitoring
            import api.mqtt as mqtt
            
            # Initialize MQTT client
            mqtt_client = mqtt.AnkerSolixMQTTClient(
                email=user(),
                password=password(),
                countryId=country(),
                logger=logging.getLogger(__name__)
            )
            
            # Power tracking variables
            last_power = None
            last_ac_enabled = None
            
            def on_message(topic, message):
                nonlocal last_power, last_ac_enabled
                
                try:
                    # Parse message data
                    data = mqtt_client.decode_message(message)
                    if not data or data.get('device_sn') != device_sn:
                        return
                    
                    # Look for power consumption data
                    decoded = data.get('decoded', {})
                    
                    # Check AC power consumption (field a3 in 0421 messages)
                    ac_power = None
                    ac_enabled = None
                    
                    # Check for AC power data in different message types
                    if 'ac_power_consumption' in decoded:
                        # This is from 0401 message type
                        ac_power = decoded['ac_power_consumption']
                        ac_enabled = decoded.get('ac_output_enabled', None)
                    elif 'usb_output_power' in decoded:
                        # This is from 0421 message type - extract AC power from binary data
                        ac_data = decoded.get('ac_power_consumption')
                        if ac_data and isinstance(ac_data, bytes) and len(ac_data) >= 4:
                            # Extract power from first 4 bytes (little endian)
                            ac_power = int.from_bytes(ac_data[:4], byteorder='little')
                    
                    # Update display if power changed
                    if ac_power is not None and ac_power != last_power:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        if ac_power == 0:
                            status = "🔴 OFF" if ac_enabled == 0 else "⭕ IDLE"
                            print(f"[{timestamp}] AC Power: {ac_power:4d}W  {status}")
                        else:
                            print(f"[{timestamp}] AC Power: {ac_power:4d}W  🟢 ACTIVE")
                        
                        last_power = ac_power
                        last_ac_enabled = ac_enabled
                        
                except Exception as e:
                    # Silently ignore decode errors
                    pass
            
            # Set up MQTT callback
            mqtt_client.set_message_callback(on_message)
            
            # Connect and subscribe
            await mqtt_client.connect()
            await mqtt_client.subscribe_device(device_sn)
            
            print("⏳ Waiting for power data... (this may take a few seconds)")
            print()
            
            # Keep monitoring
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure your F3000 is online and MQTT is enabled")

if __name__ == "__main__":
    try:
        asyncio.run(monitor_f3000_power())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")