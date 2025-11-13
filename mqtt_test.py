#!/usr/bin/env python3
"""
Simple MQTT Test - Just show if we get any messages at all
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

def simple_message_callback(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Just print that we got a message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] 📨 MQTT Message received!")
    print(f"   Topic: {topic}")
    print(f"   Data length: {len(data) if data else 0} bytes")
    print()

async def test_mqtt():
    """Test if we can receive any MQTT messages"""
    
    print("🔬 Simple MQTT Test")
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
                
            device_sn = device_selected['device_sn']
            print(f"✅ Found F3000: {device_sn}")
            
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ Failed to start MQTT session")
                return
                
            print("✅ MQTT session started")
            
            topics = set()
            if prefix := mqtt_session.get_topic_prefix(deviceDict=device_selected):
                topics.add(f"{prefix}#")  # Note: no trailing slash
                print(f"📡 Subscribed to: {prefix}#")
            
            # Start WITHOUT real-time triggers like original mqtt_monitor
            trigger_devices = set()
            print(f"🔔 Real-time trigger: OFF (matches original mqtt_monitor)")
            
            print("\n⏳ Waiting for ANY MQTT messages...")
            print("   (Should see messages within 10-20 seconds)")
            print("   Press Ctrl+C to stop")
            print()
            
            poller_task = asyncio.create_task(
                mqtt_session.message_poller(
                    topics=topics,
                    trigger_devices=trigger_devices,
                    msg_callback=simple_message_callback,
                    timeout=120,  # Wait longer
                )
            )
            
            try:
                await poller_task
            except asyncio.CancelledError:
                print("📊 Test completed")
                
        except KeyboardInterrupt:
            print("\n👋 Test stopped by user")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(test_mqtt())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")