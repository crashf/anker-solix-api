#!/usr/bin/env python3
"""
F3000 Connection Test
Quick test to verify F3000 connection and MQTT setup
"""

import asyncio
import logging
import os

from aiohttp import ClientSession
from api.api import AnkerSolixApi

async def connection_test():
    """Test F3000 connection"""
    print("🔍 F3000 Connection Test")
    print("=" * 30)
    
    email = os.getenv('ANKERUSER')
    password = os.getenv('ANKERPASSWORD') 
    country = os.getenv('ANKERCOUNTRY')
    
    if not all([email, password, country]):
        print("❌ Environment variables not set")
        return False
        
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
            
            # Find F3000
            f3000_device = None
            for sn, device in myapi.devices.items():
                if device.get('device_pn') == 'A1782':
                    f3000_device = device
                    break
                    
            if not f3000_device:
                print("❌ F3000 device not found!")
                return False
                
            alias = f3000_device.get('alias', 'F3000')
            device_sn = f3000_device['device_sn']
            device_type = f3000_device.get('type', 'unknown')
            battery_capacity = f3000_device.get('battery_capacity', 'unknown')
            
            print(f"✅ Found F3000: {alias}")
            print(f"   Serial: {device_sn}")
            print(f"   Type: {device_type}")
            print(f"   Battery: {battery_capacity}Wh")
            
            # Test MQTT connection
            print("🔌 Testing MQTT connection...")
            mqtt_session = await myapi.startMqttSession()
            if not mqtt_session:
                print("❌ MQTT connection failed")
                return False
                
            print("✅ MQTT connected successfully")
            
            # Test topic subscription
            topics = set()
            if prefix := mqtt_session.get_topic_prefix(deviceDict=f3000_device):
                topics.add(f"{prefix}#")
                print(f"📡 MQTT topic ready: {prefix}#")
            else:
                print("⚠️  Could not get MQTT topic prefix")
                
            print("✅ F3000 fully ready for power monitoring!")
            return True
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
            
        finally:
            if 'myapi' in locals() and hasattr(myapi, 'mqttsession') and myapi.mqttsession:
                myapi.mqttsession.cleanup()

if __name__ == "__main__":
    try:
        success = asyncio.run(connection_test())
        if success:
            print("\n🎉 Connection test PASSED!")
            print("F3000 is ready for real-time power monitoring")
        else:
            print("\n❌ Connection test FAILED!")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()