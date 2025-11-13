# F3000 Standalone - Production Examples

This directory contains production-ready JSON examples for the SOLIX F3000 Portable Power Station (A1782) integration with the Anker Solix API.

## Quick Start

```python
# In test_api.py or your code:
TESTAPIFROMJSON = True
JSONFOLDER = "F3000_Standalone"

# Device will be automatically detected as:
# - Type: solarbank_pps  
# - Capacity: 3072Wh
# - Virtual Site: virtual-9JVB42LXXXXX
```

## Features Supported

✅ **Device Detection**: Automatic recognition and categorization  
✅ **Power Monitoring**: AC outlets (3x), USB ports (4x), total load tracking  
✅ **Battery Management**: Level, temperature, charge/discharge monitoring  
✅ **MQTT Protocol**: Full message decoding (see `mqtt_*.json` examples)  
✅ **Virtual Sites**: Standalone operation with energy statistics  
✅ **API Integration**: Works with all main API polling methods  

## Real-world Example Data

The JSON examples reflect actual F3000 operation:
- AC Power: 245W (AC1: 118W, AC2: 127W, AC3: 0W)
- USB Power: 6W (smart management active on USB2 only)  
- Battery: 85% charge, 23.5°C temperature, 251W discharge
- Input: 0W (not charging)

## Files Overview

- `api_*.json`: Core API response data
- `device_attrs_*.json`: Device configuration and current status
- `mqtt_*.json`: MQTT message examples with field documentation  
- `setup.txt`: Device specifications and test configuration
- `config.json`: Integration test parameters

## Integration Status

This is a **production-ready** integration as of January 2025. All F3000 devices should work with the main Anker Solix API using these patterns.

For detailed research background, see `../F3000_Research_Archive/`.