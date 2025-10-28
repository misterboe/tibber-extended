#!/usr/bin/env python3
"""Test Tibber API response."""
import json
import os
import sys
import requests
from pathlib import Path

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    dotenv_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path)
except ImportError:
    pass  # python-dotenv not installed, will use os.getenv directly

TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
API_KEY = os.getenv("TIBBER_API_KEY")

if not API_KEY:
    print("ERROR: TIBBER_API_KEY not found!")
    print("Please set the TIBBER_API_KEY environment variable or create a .env file with:")
    print("TIBBER_API_KEY=your_api_key_here")
    print("\nGet your API key from: https://developer.tibber.com/")
    sys.exit(1)

QUERY = """
{
  viewer {
    homes {
      id
      appNickname
      currentSubscription {
        priceInfo {
          current {
            total
            energy
            tax
            startsAt
            level
          }
        }
      }
    }
  }
}
"""

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(
    TIBBER_API_URL,
    json={"query": QUERY},
    headers=headers,
    timeout=10,
)

print("Status Code:", response.status_code)
print("\nJSON Response:")
print(json.dumps(response.json(), indent=2))

# Check if we have level data
data = response.json()
if "data" in data and "viewer" in data["data"]:
    homes = data["data"]["viewer"]["homes"]
    for home in homes:
        print(f"\n=== Home: {home.get('appNickname', 'Unknown')} ===")
        current = home["currentSubscription"]["priceInfo"]["current"]
        print(f"Current Price: {current.get('total')} EUR/kWh")
        print(f"Level: {current.get('level')}")
        print(f"Starts At: {current.get('startsAt')}")
