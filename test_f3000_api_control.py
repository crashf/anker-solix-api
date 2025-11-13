#!/usr/bin/env python3
"""F3000 AC Control via API Attributes"""

import asyncio
from aiohttp import ClientSession

import common
from api import api

# Setup logging
CONSOLE = common.CONSOLE

async def test_api_ac_control():
    """Test AC control using the proper API set_device_attributes method."""
    CONSOLE.info("F3000 AC Control via API Attributes")
    CONSOLE.info("=" * 50)
    
    user = common.user()
    password = common.password()
    country = common.country()
    
    async with ClientSession() as websession:
        myapi = api.AnkerSolixApi(
            email=user,
            password=password,
            countryId=country,
            websession=websession,
            logger=CONSOLE
        )
        
        # Connect and find device
        await myapi.update_sites()
        await myapi.update_device_details()
        
        f3000_devices = [
            dev for dev in myapi.devices.values() 
            if dev.get('device_pn') == 'A1782'
        ]
        
        if not f3000_devices:
            CONSOLE.error("No F3000 found!")
            return
        
        device_dict = f3000_devices[0]
        device_sn = device_dict.get('device_sn')
        CONSOLE.info(f"Found F3000: {device_sn}")
        
        # First, let's see what attributes the device currently has
        CONSOLE.info("\n1. Getting current device attributes...")
        try:
            current_attrs = await myapi.get_device_attributes(
                deviceSn=device_sn,
                attributes=[]  # Get all attributes
            )
            CONSOLE.info(f"Current attributes: {current_attrs}")
        except Exception as e:
            CONSOLE.error(f"Error getting attributes: {e}")
        
        # Now try to set AC control attributes
        test_attributes = [
            # Try different possible AC control attribute names
            {"ac_output_enable": True},
            {"ac_output_enable": 1},
            {"ac_power_enable": True},
            {"ac_power_enable": 1},
            {"output_enable": True},
            {"output_enable": 1},
            {"ac_enable": True},
            {"ac_enable": 1},
            # Try with False/0 to disable
            {"ac_output_enable": False},
            {"ac_output_enable": 0},
        ]
        
        for i, attrs in enumerate(test_attributes):
            CONSOLE.info(f"\n{i+2}. Testing attribute: {attrs}")
            try:
                result = await myapi.set_device_attributes(
                    deviceSn=device_sn,
                    attributes=attrs
                )
                CONSOLE.info(f"Result: {result}")
                await asyncio.sleep(2)
                
            except Exception as e:
                CONSOLE.error(f"Error: {e}")
        
        CONSOLE.info("\nTest completed - check AC output!")

if __name__ == "__main__":
    asyncio.run(test_api_ac_control())