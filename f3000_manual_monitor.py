#!/usr/bin/env python3
"""
F3000 Manual Power Monitor
Run this when you have active load connected (~600W)
Enter credentials manually and shows power readings
"""

import asyncio
from datetime import datetime
import logging

from aiohttp import ClientSession
from api.api import AnkerSolixApi

# Your current power reading
current_power = -1

def power_callback(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Extract power from MQTT - based on successful analysis"""
    global current_power
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    topic_name = topic.split('/')[-1]
    
    print(f"[{timestamp}] 📨 {topic_name} ({len(data) if data else 0} bytes)")
    
    if isinstance(data, bytes) and len(data) > 10:
        hex_string = data.hex(':')
        hex_parts = hex_string.split(':')
        
        # Show hex preview for debugging
        if len(hex_parts) <= 20:
            print(f"   Hex: {hex_string}")
        else:
            preview = ':'.join(hex_parts[:15])
            print(f"   Hex: {preview}...")
        
        # Look for the proven power patterns from our analysis:
        # We saw: 6a:02 = 618W, 66:02 = 614W, 63:02 = 611W
        for i in range(len(hex_parts) - 1):
            if i + 1 < len(hex_parts) and hex_parts[i+1] == '02':
                power_hex = hex_parts[i]
                try:
                    power_val = int(power_hex, 16)
                    
                    # Based on observed patterns:
                    # 0x6a (106) = 618W
                    # 0x66 (102) = 614W  
                    # 0x63 (99) = 611W
                    # Linear relationship: hex * ~6 - offset
                    
                    if 50 <= power_val <= 150:  # Range that could give us meaningful power readings
                        # Calculate power based on observed pattern
                        estimated_power = (power_val - 40) * 10  # Rough approximation
                        
                        if 100 <= estimated_power <= 1000:  # Reasonable power range
                            print(f"   🔍 Power pattern: {power_hex}:02 → {power_val} decimal → ~{estimated_power}W")
                            
                            if abs(estimated_power - current_power) > 10:  # Significant change
                                status = "🔴 OFF" if estimated_power < 100 else "🟢 ACTIVE"
                                print(f"\n>>> AC POWER UPDATE: {estimated_power}W  {status} <<<")
                                print(f"    (Pattern {power_hex}:02 from {topic_name})\n")
                                current_power = estimated_power
                        
                except ValueError:
                    pass

async def manual_monitor():
    """Monitor F3000 power with manual credentials"""
    
    print("🔋 F3000 Manual Power Monitor")
    print("=" * 35)
    print("📋 Instructions:")
    print("1. Make sure your load is connected and running")
    print("2. Enter your Anker credentials when prompted") 
    print("3. Watch for power pattern analysis")
    print("4. Press Ctrl+C to stop")
    print()
    
    # Get credentials manually
    email = input("Username (email): ")
    if not email.strip():
        print("❌ Email required")
        return
        
    import getpass
    password = getpass.getpass("Password: ")
    if not password.strip():
        print("❌ Password required")
        return
        
    country = input("Country (CA/US/DE/etc): ").upper()
    if not country.strip():
        country = "CA"
    
    async with ClientSession() as websession:
        try:
            myapi = AnkerSolixApi(
                email=email,
                password=password,
                countryId=country,
                websession=websession,
                logger=logging.getLogger(__name__)
            )
            
            print("🔐 Authenticating...")
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
                
            print("✅ MQTT connected")
            
            topics = set()
            if prefix := mqtt_session.get_topic_prefix(deviceDict=device_selected):
                topics.add(f"{prefix}#")
            
            # Start without real-time trigger first
            trigger_devices = set()
            
            print()
            print("📊 Live Power Analysis")
            print("=" * 25)
            print()
            
            # Start monitoring
            poller_task = asyncio.create_task(
                mqtt_session.message_poller(
                    topics=topics,
                    trigger_devices=trigger_devices,
                    msg_callback=power_callback,
                    timeout=60,
                )
            )
            
            print("⏳ Monitoring MQTT messages...")
            print("   Looking for power patterns like: 6a:02, 66:02, 63:02")
            print("   These should correspond to ~600W+ readings")
            print()
            
            # Start a secondary task to enable real-time trigger after delay
            async def enable_realtime():
                await asyncio.sleep(20)  # Wait 20 seconds
                if not trigger_devices:  # If not already enabled
                    print("⚡ Enabling real-time trigger for more frequent updates...")
                    trigger_devices.add(device_sn)
            
            realtime_task = asyncio.create_task(enable_realtime())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [poller_task, realtime_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # If the real-time task completed, restart monitoring with trigger enabled
            if realtime_task in done:
                # Cancel old poller
                poller_task.cancel()
                try:
                    await poller_task
                except asyncio.CancelledError:
                    pass
                
                # Start new poller with real-time trigger
                poller_task = asyncio.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=power_callback,
                        timeout=120,
                    )
                )
                await poller_task
            else:
                # Original poller completed
                realtime_task.cancel()
                try:
                    await realtime_task
                except asyncio.CancelledError:
                    pass
                
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(manual_monitor())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")