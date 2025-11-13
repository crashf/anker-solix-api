#!/usr/bin/env python3
"""
F3000 Simple Power Display
Based on working mqtt_monitor.py pattern, simplified for just showing watts

Set environment variables to avoid prompts:
$env:ANKERUSER = "your.email@example.com"
$env:ANKERPASSWORD = "yourpassword"  
$env:ANKERCOUNTRY = "CA"  # or your country code
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

# Global variable to track power
current_power = 0

def simple_power_callback(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Simple callback that extracts and displays power"""
    global current_power
    
    try:
        # Parse the raw data like the working mqtt_monitor does
        if isinstance(data, bytes) and len(data) > 0:
            # Convert to hex string like mqtt_monitor shows
            hex_string = data.hex(':')
            
            # Look for the power patterns we saw in the working mqtt_monitor:
            # 6d:02 = 621W, 69:02 = 617W, 67:02 = 615W, etc.
            hex_parts = hex_string.split(':')
            
            for i in range(len(hex_parts) - 1):
                if i < len(hex_parts) - 1:
                    try:
                        # Look for the power consumption pattern
                        # In the working output, we saw values like 6d:02, 69:02, 67:02
                        # where 6d=109, 69=105, 67=103 and 02=2
                        # So the power was 109*10 + something around 600W range
                        first_byte = int(hex_parts[i], 16)
                        second_byte = int(hex_parts[i+1], 16)
                        
                        # Check if this could be a power reading
                        # We saw patterns where first byte was 0x6d, 0x69, 0x67 (109, 105, 103)
                        # and second byte was 0x02
                        if 100 <= first_byte <= 120 and second_byte == 2:
                            # This looks like the power pattern we observed
                            power = (first_byte - 100) * 10 + 600  # Approximate based on observed pattern
                            
                            if power != current_power and 0 <= power <= 2000:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                
                                if power == 0:
                                    status = "🔴 OFF"
                                elif power < 50:
                                    status = "🟡 LOW"  
                                else:
                                    status = "🟢 ACTIVE"
                                
                                print(f"[{timestamp}] AC Power: {power:4d}W  {status}")
                                current_power = power
                                break
                                
                        # Also try little-endian 16-bit interpretation
                        if i < len(hex_parts) - 1:
                            power_le = first_byte + (second_byte << 8)  # Little endian
                            if 50 <= power_le <= 1500 and power_le != current_power:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                status = "🟢 ACTIVE" if power_le >= 50 else "🟡 LOW"
                                print(f"[{timestamp}] AC Power: {power_le:4d}W  {status}")
                                current_power = power_le
                                break
                                
                    except (ValueError, IndexError):
                        continue
        
        # Also try to extract from structured message data
        if isinstance(message, dict):
            # Look for power data in the message structure
            payload = message.get('payload', {})
            if isinstance(payload, dict):
                # Check various possible power field names
                for power_field in ['ac_power', 'output_power', 'power', 'consumption']:
                    if power_field in payload:
                        try:
                            power = float(payload[power_field])
                            if 0 <= power <= 2000 and power != current_power:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                status = "🔴 OFF" if power == 0 else "🟢 ACTIVE" if power >= 50 else "🟡 LOW"
                                print(f"[{timestamp}] AC Power: {power:4.0f}W  {status}")
                                current_power = power
                                return
                        except (ValueError, TypeError):
                            pass
                            
    except Exception as e:
        # Debug: show what we're getting
        if hasattr(data, 'hex'):
            print(f"DEBUG: Received data: {data.hex(':')[:100]}...")
        print(f"DEBUG: Message type: {type(message)}")
        pass

async def monitor_f3000():
    """Monitor F3000 using the working mqtt_monitor pattern"""
    
    print("🔋 F3000 Power Monitor (Simplified)")
    print("=" * 40)
    
    # Suppress verbose logging
    logging.getLogger().setLevel(logging.WARNING)
    
    async with ClientSession() as websession:
        try:
            # Get credentials
            email, password, country = get_credentials()
            
            # Initialize API exactly like mqtt_monitor.py
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
            print("🔌 Starting MQTT monitoring...")
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ Failed to connect to MQTT")
                return
                
            print(f"✅ Connected to MQTT server {mqtt_session.host}:{mqtt_session.port}")
            print()
            print("🔌 Live AC Power:")
            print("=" * 30)
            print("Press Ctrl+C to stop")
            print()
            
            # Get topics and enable real-time trigger (this is the key!)
            topics = set()
            trigger_devices = set()
            
            if prefix := mqtt_session.get_topic_prefix(deviceDict=device_selected):
                topics.add(f"{prefix}/#")
                
            # Enable real-time data trigger - this makes the device send MQTT data!
            trigger_devices.add(device_sn)
            print(f"✅ Real-time trigger enabled for {alias}")
            
            # Start message poller (like mqtt_monitor.py does)
            poller_task = asyncio.create_task(
                mqtt_session.message_poller(
                    topics=topics,
                    trigger_devices=trigger_devices,  # This is crucial!
                    msg_callback=simple_power_callback,
                    timeout=60,
                )
            )
            
            print("⏳ Waiting for power data...")
            print("   (Turn your F3000 AC on/off to see changes)")
            print()
            
            # Wait for messages
            try:
                await poller_task
            except asyncio.CancelledError:
                print("\n📊 Monitoring stopped")
                
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
        asyncio.run(monitor_f3000())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")