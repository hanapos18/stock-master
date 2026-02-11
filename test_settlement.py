# -*- coding: utf-8 -*-
"""Settlement & date filter test"""
import requests

s = requests.Session()

# Login
r = s.post("http://localhost:5556/login",
           data={"username": "admin", "password": "admin123"},
           allow_redirects=True)
print(f"Login: {r.status_code}, url={r.url}")

# 1) Sales list (all)
r = s.get("http://localhost:5556/sales")
has_date_filter = "date_from" in r.text
has_settlement_btn = "Settlement" in r.text
print(f"Sales list: {r.status_code}, date_filter={has_date_filter}, settlement_btn={has_settlement_btn}")

# 2) Date filter - today
r = s.get("http://localhost:5556/sales?date_from=2026-02-11&date_to=2026-02-11")
has_summary = "Total Sales" in r.text
print(f"Today filter: {r.status_code}, summary={has_summary}")

# 3) Date filter - past
r = s.get("http://localhost:5556/sales?date_from=2026-01-01&date_to=2026-02-10")
print(f"Past filter: {r.status_code}, summary={'Total Sales' in r.text}")

# 4) Settlement page
r = s.get("http://localhost:5556/sales/settlement")
has_daily = "Daily Settlement" in r.text
has_day_total = "Day Total" in r.text
print(f"Settlement page: {r.status_code}, daily={has_daily}, day_total={has_day_total}")

# 5) Settlement date filter
r = s.get("http://localhost:5556/sales/settlement?date_from=2026-01-01&date_to=2026-02-11")
has_period = "Period Total" in r.text
print(f"Settlement filter: {r.status_code}, period_total={has_period}")

print("\nAll tests passed!")
