# -*- coding: utf-8 -*-
"""Stock Count - restaurant full count & mart coverage test"""
import requests

BASE = "http://localhost:5556"

def login(username, password):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": password}, allow_redirects=True)
    return s, r

print("=" * 60)
print("1. Login as admin")
print("=" * 60)
s, r = login("admin", "admin123")
print(f"   Login: {r.status_code}")

# Check business type
r = s.get(f"{BASE}/stock-count/create")
is_restaurant = "Restaurant Mode" in r.text
is_mart = "Mart Mode" in r.text
print(f"   Create page: restaurant={is_restaurant}, mart={is_mart}")

print()
print("=" * 60)
print("2. Stock Count List")
print("=" * 60)
r = s.get(f"{BASE}/stock-count")
has_list = "Stock Count Reports" in r.text
print(f"   List: {r.status_code}, ok={has_list}")

if is_restaurant:
    print()
    print("=" * 60)
    print("3. Restaurant: Full Count")
    print("=" * 60)
    # Create full stock count
    r = s.post(f"{BASE}/stock-count/create", data={
        "mode": "full",
        "count_date": "2026-02-11",
        "memo": "Test full count",
    }, allow_redirects=True)
    has_edit = "Actual" in r.text
    has_full_badge = "Full Count" in r.text or "All Products" in r.text
    # Count items on page
    import re
    actual_fields = re.findall(r'name="actual_\d+"', r.text)
    print(f"   Create full count: {r.status_code}, edit_page={has_edit}, items={len(actual_fields)}")

    if has_edit and len(actual_fields) > 0:
        # Check category grouping
        cat_headers = re.findall(r'bi-tag', r.text)
        print(f"   Category groups found: {len(cat_headers)}")

        # View the count
        count_id_match = re.search(r'/stock-count/(\d+)/edit', r.url)
        if count_id_match:
            count_id = count_id_match.group(1)
            r = s.get(f"{BASE}/stock-count/{count_id}")
            has_summary = "Total Items" in r.text
            has_match = "Match" in r.text
            print(f"   View page: summary={has_summary}, match_count={has_match}")
else:
    print()
    print("=" * 60)
    print("3. Mart: Category-based Count")
    print("=" * 60)
    print("   Mart mode - category-based (existing flow)")

print()
print("=" * 60)
print("4. Coverage Report")
print("=" * 60)
r = s.get(f"{BASE}/stock-count/coverage")
has_coverage = "Coverage Report" in r.text or "Coverage" in r.text
has_progress = "progress-bar" in r.text or "coverage_pct" in r.text
has_uncounted = "NOT Counted" in r.text or "Not Started" in r.text
print(f"   Coverage: {r.status_code}, report={has_coverage}, progress={has_progress}")
print(f"   Uncounted categories shown: {has_uncounted}")

# Check with specific date
r = s.get(f"{BASE}/stock-count/coverage?count_date=2026-02-11")
print(f"   Date filter: {r.status_code}")

print()
print("=" * 60)
print("All tests completed!")
print("=" * 60)
