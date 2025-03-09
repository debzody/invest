import requests
import pandas as pd

def get_mutual_fund_nav(scheme_code):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        
        # Extract NAV details
        scheme_name = data["meta"]["scheme_name"]
        nav_data = data["data"][0]  # Latest NAV entry
        latest_nav = nav_data["nav"]
        date = nav_data["date"]

        print(f"📈 {scheme_name}")
        print(f"🗓 Date: {date}")
        print(f"💰 NAV: ₹{latest_nav}")

    else:
        print("❌ Error fetching NAV. Check the Scheme Code.")

# Example: Fetch NAV for HDFC Technology Fund (Replace with real Scheme ID)
get_mutual_fund_nav("152059")  # Replace with actual Scheme Code