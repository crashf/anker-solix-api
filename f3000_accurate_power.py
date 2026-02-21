#!/usr/bin/env python3
"""
F3000 Accurate Power Monitor
Uses the confirmed pattern: XX:02 where XX * 6 = Watts
Based on successful pattern identification matching device screen readings
"""

import asyncio
from datetime import datetime
import logging
import os

from aiohttp import ClientSession
from api.api import AnkerSolixApi

# Track current power reading
current_ac_power = -1

def get_credentials():
    """Get credentials from environment variables"""
    email = os.getenv('ANKERUSER')
    password = os.getenv('ANKERPASSWORD') 
    country = os.getenv('ANKERCOUNTRY')
    
    if email and password and country:
        print(f"✅ Using credentials from environment")
        return email, password, country
    else:
        print("❌ Environment variables not set. Run: python setup_env.py")
        return None, None, None

def extract_accurate_power(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Extract AC power using confirmed XX:02 pattern where XX * 6 = Watts"""
    global current_ac_power
    
    if not isinstance(data, bytes) or len(data) < 10:
        return
        
    timestamp = datetime.now().strftime("%H:%M:%S")
    hex_data = data.hex(':')
    hex_parts = hex_data.split(':')
    
    # Look for the confirmed XX:02 pattern
    power_values = []
    for i in range(len(hex_parts) - 1):
        if i + 1 < len(hex_parts) and hex_parts[i+1] == '02':
            power_hex = hex_parts[i]
            try:
                power_decimal = int(power_hex, 16)
                # Use the confirmed calculation: decimal * 6 = watts
                power_watts = power_decimal * 6
                
                # Accept all reasonable power values (not just ~600W range)
                # Minimum: 0W (device off), Maximum: 3600W (theoretical F3000 max)
                if 0 <= power_watts <= 3600:  # Much broader range for all possible readings
                    power_values.append((power_hex, power_decimal, power_watts))
                    
            except ValueError:
                continue
    
    if power_values:
        # Show ALL valid power readings, not just specific ranges
        # Sort by power value to show the most likely reading first
        power_values.sort(key=lambda x: x[2])  # Sort by watts
        
        # Take the first valid power reading
        best_match = power_values[0]  # No range filtering - show whatever we get
            
        if best_match:
            hex_val, decimal_val, watts = best_match
            
            # Only update if significantly different (avoid noise)
            if abs(watts - current_ac_power) > 5:
                status = "🔴 OFF" if watts < 50 else "🟢 ACTIVE"
                print(f"[{timestamp}] AC Power: {watts:3d}W  {status}")
                print(f"           Pattern: {hex_val}:02 → {decimal_val} × 6 = {watts}W")
                current_ac_power = watts

async def accurate_power_monitor():
    """Monitor F3000 with accurate power extraction"""
    
    print("🔋 F3000 Accurate Power Monitor")
    print("=" * 40)
    print("Using confirmed pattern: XX:02 where XX × 6 = Watts")
    print("Should show ~610-615W matching your device screen")
    print()
    
    email, password, country = get_credentials()
    if not all([email, password, country]):
        return
    
    async with ClientSession() as websession:
        try:
            # Create API and connect
            myapi = AnkerSolixApi(
                email=email,
                password=password,
                countryId=country,
                websession=websession,
                logger=logging.getLogger(__name__)
            )
            
            print("🔐 Connecting to F3000...")
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000
            f3000_device = None
            for sn, device in myapi.devices.items():
                if device.get('device_pn') == 'A1782':
                    f3000_device = device
                    break
                    
            if not f3000_device:
                print("❌ F3000 device not found!")
                return
                
            alias = f3000_device.get('alias', 'F3000')
            device_sn = f3000_device['device_sn']
            print(f"✅ Found: {alias} ({device_sn})")
            
            # Start MQTT
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ MQTT connection failed")
                return
                
            print("✅ MQTT connected")
            
            # Subscribe to topics
            topics = set()
            if prefix := mqtt_session.get_topic_prefix(deviceDict=f3000_device):
                topics.add(f"{prefix}#")
            
            print()
            print("📊 Live AC Power Monitor")
            print("=" * 30)
            print("🎯 Expected: ~610-615W (matching your device screen)")
            print("📡 Pattern: XX:02 hex → XX decimal × 6 = Watts")
            print("⏳ Press Ctrl+C to stop")
            print()
            
            # Start with passive monitoring
            trigger_devices = set()
            
            try:
                # Monitor for 30 seconds passively
                print("🔍 Passive monitoring...")
                poller_task = asyncio.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=extract_accurate_power,
                        timeout=30,
                    )
                )
                await poller_task
                
            except asyncio.TimeoutError:
                pass
            
            # Enable real-time trigger for more frequent updates
            print("⚡ Enabling real-time updates...")
            trigger_devices.add(device_sn)
            
            # Continue monitoring with real-time trigger
            poller_task = asyncio.create_task(
                mqtt_session.message_poller(
                    topics=topics,
                    trigger_devices=trigger_devices,
                    msg_callback=extract_accurate_power,
                    timeout=300,  # 5 minutes
                )
            )
            
            await poller_task
                
        except KeyboardInterrupt:
            print(f"\n👋 Monitoring stopped")
            if current_ac_power >= 0:
                print(f"Last reading: {current_ac_power}W")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(accurate_power_monitor())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")