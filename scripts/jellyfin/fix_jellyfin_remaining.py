#!/usr/bin/env python3
"""Fix remaining 4 Jellyfin mismatches and create test files collection."""
import json
import urllib.request
import time

URL = "http://localhost:8096"
TOKEN = "e8202ef323524fd1acb11898fabb1869"
HEADERS = {"X-Emby-Token": TOKEN, "Content-Type": "application/json"}

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{URL}{path}", data=body, headers=HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()) if resp.headers.get("Content-Length", "1") != "0" else True
    except Exception as e:
        print(f"    API error: {e}")
        return None

def fix_movie(detected_contains, search_name, search_year=None):
    """Find a movie by detected name fragment, search TMDB, apply."""
    # Find the item
    items = api("GET", f"/Items?Recursive=true&IncludeItemTypes=Movie&SearchTerm={urllib.request.quote(detected_contains)}&Limit=5")
    if not items or not items.get("Items"):
        # Try without TMDB
        items = api("GET", f"/Items?Recursive=true&IncludeItemTypes=Movie&hasTmdbId=false&Limit=100")
        found = None
        for i in items.get("Items", []):
            if detected_contains.lower() in i.get("Path", "").lower() or detected_contains.lower() in i.get("Name", "").lower():
                found = i
                break
        if not found:
            print(f"  Could not find item matching '{detected_contains}'")
            return False
    else:
        found = items["Items"][0]

    item_id = found["Id"]
    print(f"  [{item_id[:8]}] '{found.get('Name')}' -> searching '{search_name}' ({search_year})")

    # Search TMDB
    search_info = {"SearchInfo": {"Name": search_name}}
    if search_year:
        search_info["SearchInfo"]["Year"] = search_year
    results = api("POST", "/Items/RemoteSearch/Movie", search_info)

    if not results:
        print(f"    NO RESULTS")
        return False

    best = results[0]
    print(f"    MATCH: '{best.get('Name')}' ({best.get('ProductionYear')}) TMDB={best.get('ProviderIds',{}).get('Tmdb','?')}")

    # Apply
    apply_data = json.dumps({"ReplaceAllImages": True, "ReplaceAllMetadata": True, "SearchResult": best}).encode()
    req = urllib.request.Request(
        f"{URL}/Items/RemoteSearch/Apply/{item_id}?ReplaceAllImages=true&ReplaceAllMetadata=true",
        data=apply_data, headers=HEADERS, method="POST"
    )
    resp = urllib.request.urlopen(req)
    print(f"    APPLIED (status {resp.status})")
    time.sleep(1)
    return True

# Fix the 4 remaining
print("=== Fixing remaining movies ===")
fix_movie("Star Trek Section 31", "Star Trek Section 31", 2025)
fix_movie("Explorers - Extended", "Explorers", 1985)
fix_movie("Ghost In The Shell (Oshii 1995)", "Ghost in the Shell", 1995)
fix_movie("Ghost In The Shell 2", "Ghost in the Shell 2 Innocence", 2004)

# Create collection for test files
print("\n=== Creating Tests collection ===")

# Get test file item IDs
items = api("GET", "/Items?Recursive=true&IncludeItemTypes=Movie&hasTmdbId=false&Limit=100")
test_ids = []
for item in items.get("Items", []):
    path = item.get("Path", "")
    if "/3 Video Tests/" in path:
        test_ids.append(item["Id"])
        print(f"  Test file: {item.get('Name')}")

if test_ids:
    # Create collection
    ids_param = ",".join(test_ids)
    try:
        req = urllib.request.Request(
            f"{URL}/Collections?Name=Tests&Ids={ids_param}",
            headers=HEADERS, method="POST"
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        print(f"\n  Collection created: {result.get('Id', '?')}")
    except Exception as e:
        print(f"\n  Collection error: {e}")
else:
    print("  No test files found")

print("\nDone!")
