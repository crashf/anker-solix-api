#!/usr/bin/env python3
"""
F3000 Live Data Monitor
Shows real F3000 Portable Power Station AC output wattage and other live data
"""

import asyncio
import logging
import time
from datetime import datetime
from aiohttp import ClientSession
from api import api
import common

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def print_section(title, char="="):
    """Print a formatted section header"""
    print(f"\n{char * 60}")
    print(f" {title}")
    print(f"{char * 60}")

def format_power(value, unit="W"):
    """Format power values with units"""
    if value is None or value == "" or value == "0":
        return "0W"
    try:
        power = float(value)
        if power >= 1000:
            return f"{power/1000:.2f}kW"
        return f"{int(power)}{unit}"
    except (ValueError, TypeError):
        return f"{value}{unit}"

def format_percentage(value):
    """Format percentage values"""
    if value is None or value == "":
        return "0%"
    try:
        return f"{int(float(value))}%"
    except (ValueError, TypeError):
        return f"{value}%"

async def monitor_f3000_live():
    """Monitor live F3000 data from actual device"""
    
    print_section("🔋 F3000 Live Monitor - Real Device Data", "=")
    print("🌐 Connecting to Anker Cloud API for live device data...")
    print("⚠️  Make sure your F3000 is connected to WiFi and your Anker account")
    
    # Get user credentials
    try:
        username = common.user()
        password = common.password() 
        country = common.country()
    except Exception as e:
        print(f"❌ Error getting credentials: {e}")
        print("💡 Make sure you have ANKERUSER, ANKERPASSWORD, ANKERCOUNTRY environment variables set")
        return
    
    async with ClientSession() as websession:
        myapi = api.AnkerSolixApi(username, password, country, websession, logger)
        
        try:
            print("🔐 Authenticating with Anker Cloud...")
            await myapi.async_authenticate()
            
            print("📡 Loading device data...")
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000 devices
            f3000_devices = {
                sn: device for sn, device in myapi.devices.items() 
                if device.get('device_pn') == 'A1782' or 'F3000' in device.get('name', '')
            }
            
            if not f3000_devices:
                print("❌ No F3000 devices found in your account!")
                print("💡 Make sure your F3000 is:")
                print("   • Connected to WiFi")
                print("   • Added to your Anker account via the mobile app")
                print("   • Online and accessible")
                
                # Show all devices found
                if myapi.devices:
                    print(f"\n📱 Found {len(myapi.devices)} other device(s):")
                    for sn, device in myapi.devices.items():
                        print(f"   • {device.get('name', 'Unknown')} ({device.get('device_pn', 'Unknown')})")
                else:
                    print("\n📱 No devices found at all - check your account setup")
                return
            
            print(f"✅ Found {len(f3000_devices)} F3000 device(s)")
            
            # Monitor loop
            print_section("📊 Live F3000 Monitoring (Press Ctrl+C to stop)")
            
            while True:
                # Refresh device data
                await myapi.update_device_details()
                
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"\n🕒 {current_time} - Live Data Update")
                
                for device_sn, device in f3000_devices.items():
                    print(f"\n📱 {device.get('name', 'F3000')} ({device_sn})")
                    
                    # Get live power data
                    ac_power = device.get('ac_power', '0')
                    usb_power = device.get('usb_power', '0') 
                    battery_level = device.get('battery_level', '0')
                    battery_power = device.get('battery_power', '0')
                    total_load = device.get('to_home_load', '0')
                    input_power = device.get('input_power', '0')
                    
                    # Live AC Output Details
                    print(f"⚡ AC OUTPUT: {format_power(ac_power)} TOTAL")
                    
                    # Individual AC outlets if available
                    ac_outlets = []
                    for i in range(1, 4):
                        outlet_power = device.get(f'ac{i}_power', '0')
                        if outlet_power and outlet_power != '0':
                            ac_outlets.append(f"AC{i}: {format_power(outlet_power)}")
                    
                    if ac_outlets:
                        print(f"   └─ {' | '.join(ac_outlets)}")
                    
                    # Other live data
                    print(f"🔌 USB OUTPUT: {format_power(usb_power)}")
                    print(f"📊 TOTAL LOAD: {format_power(total_load)}")
                    print(f"🔋 BATTERY: {format_percentage(battery_level)} ({format_power(battery_power, 'W')} {'charging' if float(battery_power or 0) > 0 else 'discharging' if float(battery_power or 0) < 0 else 'idle'})")
                    print(f"⬇️ INPUT: {format_power(input_power)}")
                    
                    # Connection status
                    online_status = "🟢 Online" if device.get('wifi_online') else "🔴 Offline"
                    print(f"📡 STATUS: {online_status}")
                
                print("\n⏳ Waiting 10 seconds for next update...")
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            print("\n\n⏹️ Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Error during monitoring: {e}")
            print(f"Error type: {type(e).__name__}")
            
            # Check if it's an authentication issue
            if "auth" in str(e).lower() or "login" in str(e).lower():
                print("💡 Try checking your credentials and account access")
            elif "connection" in str(e).lower() or "network" in str(e).lower():
                print("💡 Check your internet connection")
            else:
                print("💡 Check that your F3000 is online and connected to your account")

async def quick_check():
    """Quick check to see what devices are available"""
    print("🔍 Quick device check...")
    
    try:
        username = common.user()
        password = common.password() 
        country = common.country()
    except Exception as e:
        print(f"❌ Credentials error: {e}")
        return
    
    async with ClientSession() as websession:
        myapi = api.AnkerSolixApi(username, password, country, websession, logger)
        
        try:
            await myapi.async_authenticate()
            await myapi.update_sites()
            await myapi.update_device_details()
            
            print(f"Found {len(myapi.devices)} device(s) total:")
            for sn, device in myapi.devices.items():
                device_name = device.get('name', 'Unknown')
                device_pn = device.get('device_pn', 'Unknown') 
                device_type = device.get('type', 'Unknown')
                online = "🟢" if device.get('wifi_online') else "🔴"
                print(f"  {online} {device_name} ({device_pn}) - {device_type}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        asyncio.run(quick_check())
    else:
        try:
            asyncio.run(monitor_f3000_live())
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
        except Exception as e:
            print(f"\n💥 Unexpected error: {e}")
            print("Run with --check to see available devices")