#!/usr/bin/env python3
"""
Simple F3000 AC Power Monitor
Shows real-time AC power consumption in watts only
"""

import asyncio
import struct
from datetime import datetime

from aiohttp import ClientSession
from api.api import AnkerSolixApi
from common import user, password, country

async def monitor_f3000_simple():
    """Simple F3000 AC power monitor"""
    
    print("🔋 F3000 Live AC Power Monitor")
    print("=" * 40)
    
    async with ClientSession() as websession:
        try:
            # Initialize API
            myapi = AnkerSolixApi(
                email=user(),
                password=password(),
                countryId=country(),
                websession=websession
            )
            
            # Get device info
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000 device
            f3000_device = None
            for device_sn, device_info in myapi.devices.items():
                if device_info.get('device_pn') == 'A1782':
                    f3000_device = device_info
                    device_sn = device_sn
                    break
            
            if not f3000_device:
                print("❌ F3000 device not found!")
                return
                
            alias = f3000_device.get('alias', 'F3000')
            print(f"✅ Found: {alias} ({device_sn})")
            print()
            
            # Track last power reading
            last_power = None
            update_count = 0
            
            print("🔌 Live AC Power (updates every 10 seconds):")
            print("=" * 45)
            print("Press Ctrl+C to stop")
            print()
            
            while True:
                try:
                    # Update device energy data (this includes current power)
                    await myapi.update_device_energy()
                    
                    # Get current device data
                    current_device = myapi.devices.get(device_sn, {})
                    
                    # Try to get AC power from various fields
                    ac_power = None
                    
                    # Check different possible power fields
                    power_fields = [
                        'output_power',
                        'ac_power', 
                        'load_power',
                        'output_load',
                        'total_output_power'
                    ]
                    
                    for field in power_fields:
                        if field in current_device and current_device[field] is not None:
                            ac_power = current_device[field]
                            break
                    
                    # If no direct power field, try nested data
                    if ac_power is None:
                        device_loads = current_device.get('device_load', {})
                        if isinstance(device_loads, dict):
                            for load_key, load_data in device_loads.items():
                                if isinstance(load_data, dict) and 'output_power' in load_data:
                                    ac_power = load_data['output_power']
                                    break
                    
                    # Display power reading
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    update_count += 1
                    
                    if ac_power is not None:
                        if ac_power != last_power:
                            if ac_power == 0:
                                status = "🔴 OFF"
                            elif ac_power < 50:
                                status = "🟡 LOW"
                            else:
                                status = "🟢 ACTIVE"
                            
                            print(f"[{timestamp}] AC Power: {ac_power:4.0f}W  {status}")
                            last_power = ac_power
                        else:
                            # Show periodic updates even if power hasn't changed
                            if update_count % 6 == 0:  # Every minute
                                status = "🔴 OFF" if ac_power == 0 else "🟢 ACTIVE"
                                print(f"[{timestamp}] AC Power: {ac_power:4.0f}W  {status} (no change)")
                    else:
                        if update_count % 6 == 0:  # Show status every minute
                            print(f"[{timestamp}] No power data available from API")
                    
                    # Wait 10 seconds before next update
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error getting data: {e}")
                    await asyncio.sleep(10)
                    
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")
            
        except Exception as e:
            print(f"\n❌ Connection error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(monitor_f3000_simple())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")