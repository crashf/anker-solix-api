#!/usr/bin/env python3
"""
Environment Variables Setup Helper
Sets up ANKERUSER, ANKERPASSWORD, ANKERCOUNTRY for all F3000 tests
"""

import os

def setup_environment():
    """Interactive setup of environment variables"""
    print("🔧 Environment Variables Setup")
    print("=" * 35)
    print("This will help you set up environment variables for all F3000 tests")
    print()
    
    # Check current values
    current_email = os.getenv('ANKERUSER')
    current_country = os.getenv('ANKERCOUNTRY')
    has_password = bool(os.getenv('ANKERPASSWORD'))
    
    print("📋 Current Environment:")
    print(f"  ANKERUSER: {current_email if current_email else '(not set)'}")
    print(f"  ANKERPASSWORD: {'(set)' if has_password else '(not set)'}")
    print(f"  ANKERCOUNTRY: {current_country if current_country else '(not set)'}")
    print()
    
    # Get new values
    email = input(f"Email [{current_email or 'none'}]: ").strip()
    if not email and current_email:
        email = current_email
    elif not email:
        print("❌ Email is required")
        return False
    
    import getpass
    password = getpass.getpass("Password (leave empty to keep current): ").strip()
    if not password and not has_password:
        print("❌ Password is required")
        return False
    
    country = input(f"Country [{current_country or 'CA'}]: ").upper().strip()
    if not country:
        country = current_country or 'CA'
    
    # Generate PowerShell commands
    print()
    print("🚀 Environment Setup Commands (PowerShell):")
    print("=" * 50)
    print(f'$env:ANKERUSER = "{email}"')
    if password:  # Only show password command if new password provided
        print(f'$env:ANKERPASSWORD = "{password}"')
    print(f'$env:ANKERCOUNTRY = "{country}"')
    print()
    
    print("📋 To verify setup, run:")
    print('echo "User: $env:ANKERUSER, Country: $env:ANKERCOUNTRY"')
    print()
    
    print("✅ Copy and paste these commands into your PowerShell session")
    print("Then you can run any F3000 test script without entering credentials!")
    print()
    
    # Show available test scripts
    print("🧪 Available Test Scripts:")
    print("  python f3000_status_check.py    - Quick device status check")
    print("  python f3000_wait_monitor.py    - Extended MQTT monitoring")  
    print("  python f3000_manual_monitor.py  - Power pattern detection")
    print()
    
    return True

if __name__ == "__main__":
    setup_environment()