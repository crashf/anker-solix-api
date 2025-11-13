#!/usr/bin/env python3
"""
F3000 Debug Monitor - Shows what MQTT data we're actually receiving
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
    else:
        print(f"Using email from environment: {email}")
        
    if not password:
        import getpass
        password = getpass.getpass("Password: ")
    else:
        print("Using password from environment")
        
    if not country:
        country = input("Country ID (e.g. CA): ").upper()
    else:
        print(f"Using country from environment: {country}")
        
    return email, password, country

def debug_callback(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Debug callback that shows all the data we receive"""
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] === MQTT MESSAGE ===")
    print(f"Topic: {topic}")
    print(f"Model: {model}")
    print(f"Device SN: {device_sn}")
    print(f"Value Update: {valueupdate}")
    
    if isinstance(data, bytes) and len(data) > 0:
        hex_data = data.hex(':')
        print(f"Hex Data: {hex_data}")
        
        # Look for patterns similar to what we saw in mqtt_monitor
        hex_parts = hex_data.split(':')
        for i in range(min(10, len(hex_parts))):  # Show first 10 bytes
            try:
                byte_val = int(hex_parts[i], 16)
                print(f"  Byte {i}: 0x{hex_parts[i]} = {byte_val}")
            except ValueError:
                pass
    
    if isinstance(message, dict):
        print(f"Message keys: {list(message.keys())}")
        
        # Show payload if it exists
        payload = message.get('payload')
        if payload:
            print(f"Payload: {payload}")
            
    print("=" * 40)

async def debug_monitor():
    """Debug monitor to see what MQTT data we're getting"""
    
    print("🐛 F3000 Debug Monitor")
    print("=" * 40)
    
    # Suppress verbose logging
    logging.getLogger().setLevel(logging.WARNING)
    
    async with ClientSession() as websession:
        try:
            # Get credentials
            email, password, country = get_credentials()
            
            # Initialize API
            myapi = AnkerSolixApi(
                email=email,
                password=password,
                countryId=country,
                websession=websession,
                logger=logging.getLogger(__name__)
            )
            
            # Get devices
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000
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
            
            # Start MQTT session
            print("🔌 Starting MQTT debugging...")
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ Failed to connect to MQTT")
                return
                
            print(f"✅ Connected to MQTT server")
            print()
            print("📡 Raw MQTT Data:")
            print("=" * 50)
            print("Press Ctrl+C to stop")
            print()
            
            # Get topics and enable real-time trigger
            topics = set()
            trigger_devices = set()
            
            if prefix := mqtt_session.get_topic_prefix(deviceDict=device_selected):
                topics.add(f"{prefix}/#")
                print(f"Subscribed to: {prefix}/#")
            
            # Enable real-time data trigger for our device
            trigger_devices.add(device_sn)
            print(f"Enabled real-time trigger for: {device_sn}")
            
            # Start message poller with debug callback
            poller_task = asyncio.create_task(
                mqtt_session.message_poller(
                    topics=topics,
                    trigger_devices=trigger_devices,  # This enables real-time data!
                    msg_callback=debug_callback,
                    timeout=60,
                )
            )
            
            print("⏳ Waiting for MQTT messages...")
            print("   (All received data will be shown)")
            print()
            
            # Wait for messages
            try:
                await poller_task
            except asyncio.CancelledError:
                print("\n📊 Debug session stopped")
                
        except KeyboardInterrupt:
            print("\n\n👋 Stopped by user")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        finally:
            # Cleanup
            if 'myapi' in locals() and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(debug_monitor())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")