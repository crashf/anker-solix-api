#!/usr/bin/env python3
"""
F3000 Fresh Start Monitor
Starting from scratch to debug power detection
Shows ALL MQTT activity in simple format
"""

import asyncio
from datetime import datetime
import logging
import os

from aiohttp import ClientSession
from api.api import AnkerSolixApi

# Global counters
message_count = 0
power_patterns_found = 0

def get_credentials():
    """Get credentials from environment variables"""
    email = os.getenv('ANKERUSER')
    password = os.getenv('ANKERPASSWORD') 
    country = os.getenv('ANKERCOUNTRY')
    
    if email:
        print(f"✅ Using email: {email}")
    if password:
        print("✅ Using password from environment")
    if country:
        print(f"✅ Using country: {country}")
        
    return email, password, country

def simple_mqtt_callback(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Simple callback - just show what we receive"""
    global message_count, power_patterns_found
    
    message_count += 1
    timestamp = datetime.now().strftime("%H:%M:%S")
    topic_name = topic.split('/')[-1] if '/' in topic else topic
    
    print(f"\n[{timestamp}] 📨 Message #{message_count}")
    print(f"   Topic: {topic_name}")
    print(f"   Data length: {len(data) if data else 0} bytes")
    
    if data and len(data) > 0:
        hex_data = data.hex(':')
        
        # Show the raw hex data
        if len(data) <= 20:
            print(f"   Full hex: {hex_data}")
        else:
            # Show first and last 10 bytes
            hex_parts = hex_data.split(':')
            start = ':'.join(hex_parts[:10])
            end = ':'.join(hex_parts[-10:])
            print(f"   Hex start: {start}")
            print(f"   Hex end:   {end}")
            print(f"   (total {len(hex_parts)} bytes)")
        
        # Look for ANY potential power indicators
        potential_power = []
        hex_parts = hex_data.split(':')
        
        # Look for values that could represent ~600W in different encodings
        for i, byte_val in enumerate(hex_parts):
            try:
                decimal = int(byte_val, 16)
                
                # Check various potential encodings for ~600W
                if 50 <= decimal <= 200:  # Range that might encode 600W
                    # Try different calculations
                    calc1 = decimal * 10  # Simple 10x
                    calc2 = decimal * 5   # 5x scaling  
                    calc3 = decimal * 6   # 6x scaling
                    calc4 = (decimal - 50) * 15  # Offset + scaling
                    
                    for calc, method in [(calc1, "×10"), (calc2, "×5"), (calc3, "×6"), (calc4, "-50×15")]:
                        if 500 <= calc <= 800:  # Reasonable range for your load
                            potential_power.append((byte_val, decimal, calc, method, i))
                            
            except ValueError:
                continue
        
        if potential_power:
            power_patterns_found += 1
            print(f"   🔍 Potential power values found:")
            for hex_val, dec_val, calc, method, pos in potential_power:
                print(f"      Position {pos}: {hex_val} ({dec_val}) → {calc}W ({method})")
        
        # Also look for the specific patterns we found before
        if ':02' in hex_data:
            print(f"   ⭐ Found ':02' pattern (known power indicator)")
            # Find all XX:02 patterns
            for i in range(len(hex_parts) - 1):
                if hex_parts[i+1] == '02':
                    power_hex = hex_parts[i]
                    try:
                        power_val = int(power_hex, 16)
                        print(f"      {power_hex}:02 → {power_val} decimal")
                    except ValueError:
                        pass
    
    print("   " + "-" * 40)

async def fresh_start_monitor():
    """Fresh start monitoring - show everything"""
    
    print("🔄 F3000 Fresh Start Monitor")
    print("=" * 35)
    print("Starting from scratch to debug power detection")
    print()
    
    email, password, country = get_credentials()
    if not all([email, password, country]):
        print("❌ Environment variables not set. Run: python setup_env.py")
        return
    
    async with ClientSession() as websession:
        try:
            # Create API instance
            myapi = AnkerSolixApi(
                email=email,
                password=password,
                countryId=country,
                websession=websession,
                logger=logging.getLogger(__name__)
            )
            
            print("🔐 Authenticating and finding F3000...")
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000 device
            f3000_device = None
            for sn, device in myapi.devices.items():
                if device.get('device_pn') == 'A1782':
                    f3000_device = device
                    break
                    
            if not f3000_device:
                print("❌ F3000 device (A1782) not found!")
                return
                
            alias = f3000_device.get('alias', 'F3000')
            device_sn = f3000_device['device_sn']
            print(f"✅ Found: {alias} ({device_sn})")
            
            # Start MQTT session
            print("🔌 Starting MQTT session...")
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ Failed to start MQTT session")
                return
                
            print("✅ MQTT connected")
            
            # Subscribe to device topics
            topics = set()
            if prefix := mqtt_session.get_topic_prefix(deviceDict=f3000_device):
                topics.add(f"{prefix}#")
                print(f"📡 Subscribed to: {prefix}#")
            
            print()
            print("📊 Starting Fresh Monitoring")
            print("=" * 30)
            print("⚠️  Make sure you have an active load connected!")
            print("📋 What to expect:")
            print("   - MQTT messages will appear every few seconds")
            print("   - Look for potential power values in hex data")  
            print("   - Pattern ':02' is a known power indicator")
            print("   - Values 500-800W range should appear if load is active")
            print()
            print("⏳ Monitoring for 2 minutes... Press Ctrl+C to stop early")
            print()
            
            # Monitor without real-time trigger first (30 seconds)
            print("🔍 Phase 1: Passive monitoring (30 seconds)")
            trigger_devices = set()
            
            try:
                poller_task = asyncio.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=simple_mqtt_callback,
                        timeout=30,
                    )
                )
                await poller_task
                
            except asyncio.TimeoutError:
                pass
            
            print(f"\n⚡ Phase 2: Active monitoring with real-time trigger (30 seconds)")
            trigger_devices.add(device_sn)
            
            try:
                poller_task = asyncio.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=simple_mqtt_callback,
                        timeout=30,
                    )
                )
                await poller_task
                
            except asyncio.TimeoutError:
                pass
            
            # Summary
            print(f"\n📊 Monitoring Complete!")
            print(f"=" * 25)
            print(f"Total messages received: {message_count}")
            print(f"Messages with power patterns: {power_patterns_found}")
            
            if message_count == 0:
                print(f"\n❌ No MQTT messages received!")
                print(f"   Possible issues:")
                print(f"   - Device is offline or sleeping")
                print(f"   - MQTT connection problem")
                print(f"   - Device not sending data")
            elif power_patterns_found == 0:
                print(f"\n⚠️  Messages received but no power patterns found")
                print(f"   This means:")
                print(f"   - MQTT is working")
                print(f"   - But our power detection logic needs work")
                print(f"   - Need to analyze the hex data manually")
            else:
                print(f"\n✅ Found {power_patterns_found} messages with potential power data!")
                print(f"   Now we need to identify which calculation is correct")
                
        except KeyboardInterrupt:
            print(f"\n👋 Stopped by user")
            print(f"Messages received: {message_count}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(fresh_start_monitor())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")