#!/usr/bin/env python3
"""
Quick F3000 Status Check
Shows current device status via API calls
Uses environment variables: ANKERUSER, ANKERPASSWORD, ANKERCOUNTRY
"""

import asyncio
import json
import os
from aiohttp import ClientSession
from api.api import AnkerSolixApi

def get_credentials():
    """Get credentials from environment variables or prompt"""
    email = os.getenv('ANKERUSER')
    password = os.getenv('ANKERPASSWORD') 
    country = os.getenv('ANKERCOUNTRY')
    
    print("🔑 Checking credentials...")
    
    if not email:
        email = input("Email (set ANKERUSER env var): ")
    else:
        print(f"✅ Email from environment: {email}")
    
    if not password:
        import getpass
        password = getpass.getpass("Password (set ANKERPASSWORD env var): ")
    else:
        print("✅ Password from environment")
    
    if not country:
        country = input("Country (set ANKERCOUNTRY env var, e.g. CA): ").upper()
    else:
        print(f"✅ Country from environment: {country}")
        
    if not all([email, password, country]):
        print("❌ Missing credentials")
        return None, None, None
        
    return email, password, country

async def check_status():
    print("🔍 F3000 Quick Status Check")
    print("=" * 30)
    
    email, password, country = get_credentials()
    if not email:
        return
    
    async with ClientSession() as websession:
        try:
            myapi = AnkerSolixApi(email, password, country, websession)
            
            print("🔐 Checking device status...")
            await myapi.update_sites()
            await myapi.update_device_details()
            
            # Find F3000
            f3000 = None
            for sn, device in myapi.devices.items():
                if device.get('device_pn') == 'A1782':
                    f3000 = device
                    break
            
            if not f3000:
                print("❌ F3000 not found")
                return
                
            alias = f3000.get('alias', 'F3000')
            sn = f3000['device_sn']
            print(f"✅ Found: {alias} ({sn})")
            
            # Show current device data
            print("\n📊 Current Device Data:")
            print("-" * 25)
            
            # Key fields that might show power
            key_fields = [
                'ac_power', 'output_power', 'input_power', 'load_power',
                'power_consumption', 'ac_output_power', 'total_power',
                'current_power', 'inverter_power', 'battery_power'
            ]
            
            found_power_fields = []
            for field in key_fields:
                if field in f3000:
                    value = f3000[field]
                    print(f"  {field}: {value}")
                    if isinstance(value, (int, float)) and value > 0:
                        found_power_fields.append((field, value))
            
            # Show all available fields
            print(f"\n📋 All Available Fields ({len(f3000)} total):")
            print("-" * 35)
            for key, value in sorted(f3000.items()):
                if isinstance(value, (int, float, str)) and len(str(value)) < 50:
                    print(f"  {key}: {value}")
            
            # Power summary
            print(f"\n⚡ Power Summary:")
            if found_power_fields:
                print(f"  Found {len(found_power_fields)} power-related fields:")
                for field, value in found_power_fields:
                    print(f"    {field}: {value}W")
            else:
                print(f"  No non-zero power fields found")
                print(f"  Device appears to be idle or in standby")
            
            print(f"\n💡 Recommendation:")
            if found_power_fields:
                print(f"  Device shows active power - MQTT should have data")
                print(f"  Try the extended monitor: python f3000_wait_monitor.py")
            else:
                print(f"  Device shows no active power consumption")
                print(f"  Connect a load (~600W) and try again")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_status())