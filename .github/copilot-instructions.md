# Anker Solix API - AI Development Guide

## Architecture Overview

This is a Python library for interacting with Anker Solix Power devices (solar banks, inverters, smart meters, portable power stations) via their cloud API and MQTT protocols. The architecture follows a layered approach:

- **Base Layer**: `AnkerSolixBaseApi` provides common session management and caching
- **API Layer**: `AnkerSolixApi` extends base for balcony power systems using `power_service` endpoints
- **Specialized APIs**: `AnkerSolixPowerpanelApi` and `AnkerSolixHesApi` for specific device categories
- **Session Layer**: `AnkerSolixClientSession` handles authentication, encryption, and HTTP requests
- **Data Layer**: Structured caching with hierarchical relationships: account → sites → devices

## Key Patterns & Conventions

### API Session Management
Always use the session pattern with proper async context:
```python
async with ClientSession() as websession:
    myapi = api.AnkerSolixApi(email, password, country, websession, logger)
    await myapi.update_sites()  # Always call before device operations
```

### Data Polling Hierarchy
Follow this exact sequence for data collection:
1. `update_sites()` - Core system data, populates `sites`, `devices`, `account` caches
2. `update_device_details()` - Device configuration (run first, creates virtual sites for standalone devices)  
3. `update_site_details()` - Site configuration
4. `update_device_energy()` - Energy statistics (rate-limited, run sparingly)

### Cache Structure
The API maintains structured dictionaries accessible via `myapi.sites`, `myapi.devices`, `myapi.account`. Device serial numbers (`device_sn`) are primary keys, site IDs are UUIDs or `virtual-<device-sn>` format.

### Module Organization
Core functionality is split across specialized modules imported into `AnkerSolixApi`:
- `energy.py` - Energy statistics and forecasting  
- `schedule.py` - Device scheduling and load management
- `vehicle.py` - EV charging integration
- `poller.py` - Data polling implementations
- `apitypes.py` - All API endpoints, enums, and constants

## Testing & Development

### JSON-Based Testing
Extensive example data in `examples/` directories with real anonymized API responses. Use for development:
```python
TESTAPIFROMJSON = True
JSONFOLDER = "SB2_SM_ManMode_Schedule"
```

### Core Test Scripts
- `test_api.py` - Main API testing with configurable test modes
- `monitor.py` - Real-time monitoring tool with JSON fallback support  
- `export_system.py` - System data export with anonymization

### Configuration
Environment variables pattern: `ANKERUSER`, `ANKERPASSWORD`, `ANKERCOUNTRY`. See `common.py` for credential helpers.

## Critical Implementation Details

### Authentication Flow
Uses ECDH key exchange + AES-256-CBC encryption. Session tokens cached in `authcache/` directory. Authentication state managed in `AnkerSolixClientSession`.

### Rate Limiting
Energy endpoints limited to ~10-12 requests/minute (reduced from 25-30). Use `_request_delay` and `_endpoint_limit` for throttling.

### Device Type Handling
Device types determined by product codes (`device_pn`) mapped in `SolixDeviceCategory`. Virtual sites created for standalone devices in `update_device_details()`.

### MQTT Support
Experimental MQTT client in `mqtt.py` with byte data parsing in `mqtttypes.py`. Device models mapped in `mqttmap.py` for protocol support detection.

## Common Development Workflows

### Adding New Device Support
1. Add product code to `apitypes.py` enums (`SolixDeviceCategory`, `SolixDeviceCapacity`)
2. Update device-specific modules (`energy.py`, `schedule.py`) 
3. Add MQTT mapping in `mqttmap.py` if supported
4. Test with JSON exports from real devices

### Endpoint Development  
1. Add endpoint to `API_ENDPOINTS` in `apitypes.py`
2. Implement method following async/session patterns
3. Use `_update_dev()` or `_update_site()` for cache consistency
4. Test with multiple device configurations from `examples/`

### Error Handling
Follow the pattern: catch `ClientError`, check for authentication expiry, use retry logic with `_retry_attempt`. See `session.py` error handling patterns.

## Adding New Devices

### Device Addition Workflow
1. **Identify Device Details**: Product code (PN), device type, battery capacity, MQTT support
2. **Update Core Definitions**: Add to `apitypes.py` classes (`SolixDeviceCapacity`, `SolixDeviceCategory`, device-specific metrics)
3. **Export Device Data**: Use `export_system.py` to create JSON test examples
4. **JSON-Based Testing**: Set `TESTAPIFROMJSON = True` and test with example data first
5. **Add Device Logic**: Update specialized modules (`energy.py`, `schedule.py`) for device-specific features
6. **MQTT Support**: Add mapping to `mqttmap.py` if device supports MQTT
7. **Validation**: Test with `test_api.py`, `monitor.py`, and real API calls

### Core Type Definitions Pattern
```python
# In apitypes.py - Add battery capacity
class SolixDeviceCapacity:
    A17XX: int = 3000  # Device Name - capacity in Wh

# Add device category with generation suffix  
class SolixDeviceCategory:
    A17XX: str = SolixDeviceType.SOLARBANK.value + "_4"

# Add trackable metrics for device type
class SolarbankDeviceMetrics:
    A17XX: ClassVar[set[str]] = {"solar_power_1", "battery_power"}
```

### Testing Strategy
- Always start with JSON examples to avoid rate limits
- Use `export_system.py` for anonymized real device data  
- Test detection with `update_device_details()` 
- Verify cache structure in `myapi.devices`
- Use `monitor.py` for real-time validation

## F3000 Portable Power Station Support

### Device Specifications
- **Product Code**: A1782 (SOLIX F3000 Portable Power Station)
- **Category**: SOLARBANK_PPS (Solarbank + Portable Power Station)
- **Battery Capacity**: 3072Wh LiFePO4
- **AC Output**: 3 outlets, 3000W max combined
- **USB Output**: 4 smart-managed ports
- **MQTT Protocol**: Fully supported with 5 message types

### MQTT Protocol Support
F3000 has comprehensive MQTT protocol decoding in `mqttmap.py`:

```python
# Message Types Supported:
- 0857: Main status updates (AC/USB power, battery level, total load)
- 0401: Individual outlet monitoring (per-outlet AC, USB, car port power)  
- 0421: Device configuration (limits, settings, detailed parameters)
- 0889: Battery and system data (temperature, health, charging status)
- 0301: Command responses (AC control acknowledgments, setting confirmations)
```

### API Integration Features
- **Device Detection**: Automatic recognition as `solarbank_pps` type
- **Metrics Tracking**: 17+ real-time metrics including per-outlet monitoring
- **Virtual Sites**: Standalone operation with `virtual-<device_sn>` site creation
- **JSON Testing**: Complete example data in `examples/F3000_Standalone/`
- **Monitoring**: Real-time power flow tracking with smart USB management

### Usage Examples
```python
# Test with JSON examples
TESTAPIFROMJSON = True
JSONFOLDER = "F3000_Standalone" 

# Real-time monitoring shows:
# - AC Power: 245W (AC1: 118W, AC2: 127W, AC3: 0W)
# - USB Power: 6W (smart management reduces idle ports)
# - Battery: 85% at 23.5°C, discharging 251W total
```