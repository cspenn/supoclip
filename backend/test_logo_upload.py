#!/usr/bin/env python3
"""Test script to verify logo upload fix.

This script tests that the backend now accepts user_id header (with underscore)
after the fix to src/dependencies.py.
"""

import requests
from pathlib import Path

# Configuration
API_URL = "http://localhost:8008"
TEST_USER_ID = "local-user"
LOGO_PATH = Path(__file__).parent / "docs" / "TI_Primary_2Color_Reverse.png"

def test_logo_upload():
    """Test logo upload with user_id header (underscore format)."""
    print(f"Testing logo upload to {API_URL}/upload-logo")
    print(f"User ID: {TEST_USER_ID}")
    print(f"Logo file: {LOGO_PATH}")

    if not LOGO_PATH.exists():
        print(f"❌ ERROR: Logo file not found at {LOGO_PATH}")
        return False

    print(f"✅ Logo file found ({LOGO_PATH.stat().st_size} bytes)")

    # Prepare request
    headers = {
        "user_id": TEST_USER_ID,  # Using underscore format (the fix)
    }

    files = {
        "logo": ("TI_Primary_2Color_Reverse.png", open(LOGO_PATH, "rb"), "image/png")
    }

    data = {
        "corner_position": "bottom-right"
    }

    print("\n📤 Sending request...")
    print(f"   Headers: {headers}")
    print(f"   Data: {data}")

    try:
        response = requests.post(
            f"{API_URL}/upload-logo",
            headers=headers,
            files=files,
            data=data,
            timeout=10
        )

        print(f"\n📥 Response status: {response.status_code}")

        if response.status_code == 200:
            print("✅ SUCCESS! Logo uploaded successfully")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ FAILED with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Could not connect to {API_URL}")
        print("   Make sure the backend server is running on port 8008")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False
    finally:
        files["logo"][1].close()

if __name__ == "__main__":
    print("=" * 60)
    print("Logo Upload Test - Verifying user_id header fix")
    print("=" * 60)
    print()

    success = test_logo_upload()

    print()
    print("=" * 60)
    if success:
        print("✅ TEST PASSED - Logo upload is working!")
    else:
        print("❌ TEST FAILED - Logo upload is not working")
    print("=" * 60)
