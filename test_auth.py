#!/usr/bin/env python3
"""Simple script to test Garmin authentication"""
from garminconnect import Garmin
from getpass import getpass

print("Testing Garmin Connect Authentication")
print("=" * 50)

email = input("Enter your Garmin email: ").strip()
password = getpass("Enter your Garmin password: ")

print("\nAttempting to login...")
try:
    client = Garmin(email, password)
    client.login()
    print("✓ SUCCESS! Authentication worked.")
    print(f"✓ Logged in as: {client.get_full_name()}")
    print("\nYou can now use these credentials in workouts.py")
except Exception as e:
    print(f"\n✗ FAILED: {e}")
    print("\nPossible issues:")
    print("1. Email or password is incorrect")
    print("2. 2FA is enabled - you may need to enter the code when prompted")
    print("3. Account may be locked or require verification")
    import traceback
    traceback.print_exc()
