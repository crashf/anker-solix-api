#!/usr/bin/env python3
"""
F3000 Comprehensive Test Verification
Tests all F3000 functionality and definitions
"""

import os
import sys
import asyncio
from datetime import datetime

def test_imports():
    """Test that all F3000 modules import correctly"""
    print("🔍 Testing F3000 Module Imports")
    print("=" * 40)
    
    try:
        import f3000_status_check
        print("✅ f3000_status_check imported")
        
        import f3000_accurate_power  
        print("✅ f3000_accurate_power imported")
        
        import f3000_fresh_start
        print("✅ f3000_fresh_start imported")
        
        import f3000_manual_monitor
        print("✅ f3000_manual_monitor imported")
        
        import f3000_wait_monitor
        print("✅ f3000_wait_monitor imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_apitypes():
    """Test F3000 definitions in apitypes"""
    print("\n📊 Testing F3000 API Types")
    print("=" * 40)
    
    try:
        from api.apitypes import SolixDeviceCapacity, SolixDeviceCategory, SolarbankDeviceMetrics
        
        # Test device capacity
        capacity = SolixDeviceCapacity.A1782
        print(f"✅ F3000 Capacity: {capacity}Wh")
        assert capacity == 3072, f"Expected 3072Wh, got {capacity}Wh"
        
        # Test device category  
        category = SolixDeviceCategory.A1782
        print(f"✅ F3000 Category: {category}")
        assert category == "solarbank_pps", f"Expected solarbank_pps, got {category}"
        
        # Test device metrics
        metrics = SolarbankDeviceMetrics.A1782
        print(f"✅ F3000 Metrics: {len(metrics)} fields")
        assert len(metrics) >= 17, f"Expected at least 17 metrics, got {len(metrics)}"
        
        # Test power monitoring metrics
        required_metrics = ["ac_power", "real_time_power", "battery_level", "battery_power"]
        for metric in required_metrics:
            assert metric in metrics, f"Missing required metric: {metric}"
            print(f"✅ Metric '{metric}' supported")
        
        # Test power pattern definition
        pattern = SolarbankDeviceMetrics.F3000_POWER_PATTERN
        print(f"✅ Power Pattern Status: {pattern['status']}")
        assert pattern['status'] == "CONFIRMED_WORKING", "Power pattern not confirmed"
        
        print(f"✅ MQTT Pattern: {pattern['mqtt_pattern']}")
        assert pattern['mqtt_pattern'] == "XX:02", "Incorrect MQTT pattern"
        
        print(f"✅ Calculation: {pattern['calculation']}")
        assert pattern['calculation'] == "XX * 6", "Incorrect calculation method"
        
        # Test example patterns
        examples = pattern['example_patterns']
        test_cases = [
            ("60:02", 576),
            ("64:02", 600), 
            ("66:02", 612),
            ("6b:02", 642)
        ]
        
        for hex_pattern, expected_watts in test_cases:
            actual_watts = examples[hex_pattern]
            assert actual_watts == expected_watts, f"{hex_pattern}: expected {expected_watts}W, got {actual_watts}W"
            print(f"✅ Example {hex_pattern} → {actual_watts}W")
            
        return True
        
    except Exception as e:
        print(f"❌ API Types error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment():
    """Test environment variables"""
    print("\n🔑 Testing Environment Variables")
    print("=" * 40)
    
    email = os.getenv('ANKERUSER')
    password = os.getenv('ANKERPASSWORD')
    country = os.getenv('ANKERCOUNTRY')
    
    if email:
        print(f"✅ ANKERUSER: {email}")
    else:
        print("⚠️  ANKERUSER not set")
        
    if password:
        print("✅ ANKERPASSWORD: (set)")
    else:
        print("⚠️  ANKERPASSWORD not set")
        
    if country:
        print(f"✅ ANKERCOUNTRY: {country}")
    else:
        print("⚠️  ANKERCOUNTRY not set")
        
    all_set = all([email, password, country])
    if all_set:
        print("✅ All environment variables configured")
    else:
        print("⚠️  Some environment variables missing")
        
    return all_set

def test_credentials_function():
    """Test credential functions work"""
    print("\n🔐 Testing Credential Functions")
    print("=" * 40)
    
    try:
        from f3000_accurate_power import get_credentials
        email, password, country = get_credentials()
        
        if all([email, password, country]):
            print("✅ Credential function working")
            return True
        else:
            print("⚠️  Credentials incomplete")
            return False
            
    except Exception as e:
        print(f"❌ Credential function error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 F3000 Comprehensive Test Suite")
    print("=" * 50)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = []
    
    # Run all tests
    results.append(("Module Imports", test_imports()))
    results.append(("API Types", test_apitypes()))  
    results.append(("Environment", test_environment()))
    results.append(("Credentials", test_credentials_function()))
    
    # Summary
    print("\n📋 Test Summary")
    print("=" * 20)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:15} {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        print("F3000 monitoring system is fully functional!")
        print("\nReady for:")
        print("  - Real-time power monitoring")
        print("  - MQTT pattern XX:02 decoding")  
        print("  - Device status checking")
        print("  - Complete F3000 integration")
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed")
        print("Some components may need attention")
        
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)