#!/usr/bin/env python3
"""
F3000 Extended Wait Monitor
Waits longer for MQTT messages and shows when they arrive
"""

import asyncio
from datetime import datetime
import logging

from aiohttp import ClientSession
from api.api import AnkerSolixApi

# Track messages received
message_count = 0
last_power = -1

def message_handler(session, topic: str, message: dict, data: bytes, model: str, device_sn: str, valueupdate: bool):
    """Handle all MQTT messages with extended analysis"""
    global message_count, last_power
    
    message_count += 1
    timestamp = datetime.now().strftime("%H:%M:%S")
    topic_name = topic.split('/')[-1]
    
    print(f"\n[{timestamp}] 📨 Message #{message_count}: {topic_name}")
    print(f"   Data length: {len(data) if data else 0} bytes")
    
    if isinstance(data, bytes) and len(data) > 0:
        hex_string = data.hex(':')
        hex_parts = hex_string.split(':')
        
        # Show full hex for short messages, preview for long ones
        if len(data) <= 30:
            print(f"   Full hex: {hex_string}")
        else:
            preview = ':'.join(hex_parts[:20])
            print(f"   Hex (first 20 bytes): {preview}...")
        
        # Look for ANY XX:02 patterns (our discovered power signature)
        power_patterns = []
        for i in range(len(hex_parts) - 1):
            if i + 1 < len(hex_parts) and hex_parts[i+1] == '02':
                power_hex = hex_parts[i]
                try:
                    power_val = int(power_hex, 16)
                    if 30 <= power_val <= 200:  # Reasonable range for power encoding
                        power_patterns.append((power_hex, power_val))
                except ValueError:
                    pass
        
        if power_patterns:
            print(f"   🔍 Found power patterns:")
            for power_hex, power_val in power_patterns:
                # Try different calculations based on our observations:
                # 6a:02 = 618W, 66:02 = 614W, 63:02 = 611W
                calc1 = power_val * 6  # Simple scaling
                calc2 = (power_val - 40) * 10  # Offset + scaling
                calc3 = power_val * 10 - 440  # Different offset
                
                print(f"      {power_hex}:02 → {power_val} decimal")
                print(f"         Calc1 (×6): {calc1}W")
                print(f"         Calc2 (×10-400): {calc2}W") 
                print(f"         Calc3 (×10-440): {calc3}W")
                
                # If any calculation is in reasonable range, highlight it
                for calc, name in [(calc1, "×6"), (calc2, "×10-400"), (calc3, "×10-440")]:
                    if 500 <= calc <= 1000:  # Range for ~600W load
                        print(f"      ⭐ {name} gives {calc}W - matches expected range!")
                        if abs(calc - last_power) > 20:
                            print(f"\n>>> POWER READING: {calc}W <<<")
                            last_power = calc
        
        # Look for specific field patterns we identified
        if 'a6:0a:04' in hex_string:
            print(f"   🎯 Found a6 field pattern!")
        if 'ff:09:21' in hex_string:
            print(f"   🎯 Found 0401 message pattern!")
    
    print(f"   ---")

async def extended_monitor():
    """Extended monitoring with longer waits"""
    
    print("🔋 F3000 Extended Wait Monitor")
    print("=" * 40)
    print("This version waits longer and shows all MQTT activity")
    print()
    
    # Get credentials
    email = input("Username (email): ")
    if not email.strip():
        print("❌ Email required")
        return
        
    import getpass
    password = getpass.getpass("Password: ")
    country = input("Country (CA): ").upper() or "CA"
    
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
                print(f"📡 Subscribed to: {prefix}#")
            
            print()
            print("📊 Extended Monitoring (3 minutes)")
            print("=" * 40)
            print("⏳ Phase 1: Passive monitoring (60 seconds)")
            print("   Waiting for natural MQTT messages...")
            print()
            
            # Phase 1: Passive monitoring (no real-time trigger)
            trigger_devices = set()
            start_time = datetime.now()
            
            try:
                poller_task = asyncio.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=message_handler,
                        timeout=60,  # 60 seconds passive
                    )
                )
                
                await poller_task
                
            except asyncio.TimeoutError:
                print(f"\n⏰ Phase 1 complete: Received {message_count} messages")
            
            # Phase 2: Active monitoring with real-time trigger
            print(f"\n⚡ Phase 2: Active monitoring with real-time trigger (60 seconds)")
            print(f"   Enabling frequent updates...")
            
            trigger_devices.add(device_sn)
            
            try:
                poller_task = asyncio.create_task(
                    mqtt_session.message_poller(
                        topics=topics,
                        trigger_devices=trigger_devices,
                        msg_callback=message_handler,
                        timeout=60,  # 60 seconds active
                    )
                )
                
                await poller_task
                
            except asyncio.TimeoutError:
                print(f"\n⏰ Phase 2 complete")
            
            # Summary
            elapsed = datetime.now() - start_time
            print(f"\n📊 Monitoring Summary:")
            print(f"   Total messages received: {message_count}")
            print(f"   Monitoring duration: {elapsed.seconds} seconds")
            print(f"   Message rate: {message_count/elapsed.seconds:.2f} msg/sec")
            
            if message_count == 0:
                print(f"\n⚠️  No messages received. Possible reasons:")
                print(f"   - F3000 is idle/sleeping (no active load)")
                print(f"   - Network connectivity issues") 
                print(f"   - Device is in power-saving mode")
                print(f"   \n💡 Try connecting a load and running again")
            else:
                print(f"\n✅ Successfully received MQTT data!")
                
        except KeyboardInterrupt:
            print(f"\n👋 Stopped by user (received {message_count} messages)")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(extended_monitor())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")