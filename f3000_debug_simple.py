#!/usr/bin/env python3
"""
Debug F3000 Power Monitor - Show what messages we're getting
"""

import asyncio
from datetime import datetime
import logging
import os

from aiohttp import ClientSession
from api.api import AnkerSolixApi

def get_credentials():
    """Get credentials from environment variables or prompt"""
    email = os.getenv('ANKERUSER')
    password = os.getenv('ANKERPASSWORD') 
    country = os.getenv('ANKERCOUNTRY')
    
    if not email:
        email = input("Username (email): ")
    if not password:
        import getpass
        password = getpass.getpass("Password: ")
    if not country:
        country = input("Country ID (e.g. CA): ").upper()
        
    return email, password, country

def debug_message_callback(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Show detailed message information"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    topic_name = topic.split('/')[-1]
    
    print(f"[{timestamp}] 📨 Topic: {topic_name} ({len(data) if data else 0} bytes)")
    
    if isinstance(data, bytes) and len(data) > 0:
        hex_string = data.hex(':')
        hex_parts = hex_string.split(':')
        
        # Show full hex data for small messages
        if len(data) <= 50:
            print(f"   Full hex: {hex_string}")
        else:
            # Show first 30 bytes for longer messages  
            preview = ':'.join(hex_parts[:30])
            print(f"   Hex preview (30 bytes): {preview}...")
        
        # Look for our known power patterns
        for i in range(len(hex_parts) - 5):
            # Pattern 1: XX:02 (from field a6)
            if i + 1 < len(hex_parts) and hex_parts[i+1] == '02':
                power_candidate = hex_parts[i]
                try:
                    power_val = int(power_candidate, 16)
                    if 50 <= power_val <= 200:  # Reasonable range for our 600W test
                        calculated = (power_val - 50) * 10
                        print(f"   Power pattern? {power_candidate}:02 → {calculated}W")
                except ValueError:
                    pass
                    
            # Pattern 2: Look for a6:0a:04 prefix
            if (i + 4 < len(hex_parts) and 
                hex_parts[i] == 'a6' and 
                hex_parts[i+1] == '0a' and 
                hex_parts[i+2] == '04'):
                power_bytes = ':'.join(hex_parts[i:i+8])
                print(f"   Found a6 field: {power_bytes}")
                
    print()

async def debug_mqtt():
    """Debug MQTT messages to see what we're getting"""
    
    print("🔬 F3000 Debug Monitor")
    print("=" * 30)
    
    async with ClientSession() as websession:
        try:
            email, password, country = get_credentials()
            
            myapi = AnkerSolixApi(
                email=email,
                password=password,
                countryId=country,
                websession=websession,
                logger=logging.getLogger(__name__)
            )
            
            await myapi.update_sites()
            await myapi.update_device_details()
            
            device_selected = None
            for sn, device in myapi.devices.items():
                if device.get('device_pn') == 'A1782':
                    device_selected = device
                    break
                    
            if not device_selected:
                print("❌ F3000 device not found!")
                return
                
            alias = device_selected.get('alias', 'F3000')
            device_sn = device_selected['device_sn']
            print(f"✅ Found: {alias} ({device_sn})")
            
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ Failed to start MQTT session")
                return
                
            print("✅ MQTT session started")
            
            topics = set()
            if prefix := mqtt_session.get_topic_prefix(deviceDict=device_selected):
                topics.add(f"{prefix}#")
                print(f"📡 Subscribed to: {prefix}#")
            
            trigger_devices = set()
            trigger_devices.add(device_sn)  # Enable real-time trigger to get more frequent updates
            print(f"🔔 Real-time trigger: ON (to force frequent updates)")
            
            print("\n📊 Watching for power data patterns...")
            print("   (With ~600W load, look for values like 6a:02, 66:02, 63:02)")
            print("   Press Ctrl+C to stop")
            print()
            
            poller_task = asyncio.create_task(
                mqtt_session.message_poller(
                    topics=topics,
                    trigger_devices=trigger_devices,
                    msg_callback=debug_message_callback,
                    timeout=120,
                )
            )
            
            try:
                await poller_task
            except asyncio.CancelledError:
                print("📊 Debug session completed")
                
        except KeyboardInterrupt:
            print("\n👋 Debug stopped by user")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(debug_mqtt())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")