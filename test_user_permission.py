# -*- coding: utf-8 -*-
"""User permission & store access test"""
import requests

BASE = "http://localhost:5556"

def login(username, password):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": password}, allow_redirects=True)
    return s, r

print("=" * 60)
print("1. Admin login (HQ - all stores)")
print("=" * 60)
s_admin, r = login("admin", "admin123")
print(f"   Login: {r.status_code}, url={r.url}")

# User management page
r = s_admin.get(f"{BASE}/users")
has_users_page = "User Management" in r.text
has_create_form = "Create New User" in r.text
print(f"   Users page: {r.status_code}, management={has_users_page}, create={has_create_form}")

# Check HQ badge and store dropdown
r = s_admin.get(f"{BASE}/")
has_hq_badge = "HQ" in r.text
has_admin_badge = "Admin" in r.text
print(f"   Dashboard: HQ={has_hq_badge}, Admin={has_admin_badge}")

# Check stores dropdown available
r2 = s_admin.get(f"{BASE}/sales")
has_settlement = "Settlement" in r2.text
print(f"   Sales page: {r2.status_code}, settlement={has_settlement}")

# Create a branch user (store_id = first store)
print()
print("=" * 60)
print("2. Create branch user")
print("=" * 60)

# Get stores list from users page
r = s_admin.get(f"{BASE}/users")
# Find first store option value
import re
store_options = re.findall(r'<option value="(\d+)">', r.text)
if store_options:
    first_store_id = store_options[0]
    print(f"   First store ID: {first_store_id}")

    # Create branch user
    r = s_admin.post(f"{BASE}/users/create", data={
        "username": "branch_test",
        "name": "Branch Tester",
        "password": "test123",
        "role": "staff",
        "store_id": first_store_id,
    }, allow_redirects=True)
    has_success = "created successfully" in r.text or "already exists" in r.text
    print(f"   Create user: {r.status_code}, result={has_success}")

    # Login as branch user
    print()
    print("=" * 60)
    print("3. Branch user login (single store)")
    print("=" * 60)
    s_branch, r = login("branch_test", "test123")
    print(f"   Login: {r.status_code}, url={r.url}")

    # Check NO store dropdown (single store access)
    r = s_branch.get(f"{BASE}/")
    has_hq = ">HQ<" in r.text
    has_staff_badge = "Staff" in r.text
    print(f"   Dashboard: HQ={has_hq}, Staff={has_staff_badge}")

    # Check sales (should only show store's sales)
    r = s_branch.get(f"{BASE}/sales")
    print(f"   Sales: {r.status_code}")

    # Check user management (should be denied)
    r = s_branch.get(f"{BASE}/users")
    denied = "Access denied" in r.text or r.url.endswith("/")
    print(f"   Users page (should deny): denied={denied}")

    # Try switch to another store (should fail)
    r = s_branch.get(f"{BASE}/switch-store/9999", allow_redirects=True)
    no_perm = "don't have permission" in r.text or "Access denied" in r.text
    print(f"   Switch to invalid store: no_perm={no_perm}")

else:
    print("   No stores found, skipping branch user test")

print()
print("=" * 60)
print("All tests completed!")
print("=" * 60)
