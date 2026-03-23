#!/usr/bin/env python3
"""Fix Jellyfin movie metadata by re-identifying mismatched movies."""
import json
import re
import os
import urllib.request
import time

JELLYFIN_URL = "http://localhost:8096"
API_TOKEN = "e8202ef323524fd1acb11898fabb1869"
HEADERS = {
    "X-Emby-Token": API_TOKEN,
    "Content-Type": "application/json",
}

def api_get(path):
    req = urllib.request.Request(f"{JELLYFIN_URL}{path}", headers=HEADERS)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def api_post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{JELLYFIN_URL}{path}", data=body, headers=HEADERS, method="POST")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read()) if resp.status == 200 else None

def extract_name_year(filename):
    """Extract movie name and year from filename like 'Movie Name (2024).mkv'"""
    base = os.path.splitext(filename)[0]
    match = re.search(r'\((\d{4})\)', base)
    if match:
        year = int(match.group(1))
        name = base[:match.start()].strip()
        return name, year
    return base, None

def main():
    # Get all movies without TMDB ID
    data = api_get("/Items?Recursive=true&IncludeItemTypes=Movie&Fields=Path,ProviderIds&hasTmdbId=false&Limit=100")
    items = data.get("Items", [])

    print(f"Found {len(items)} movies without TMDB ID")

    skipped = 0
    fixed = 0
    failed = 0

    for item in items:
        path = item.get("Path", "")
        item_id = item.get("Id", "")
        detected_name = item.get("Name", "?")

        # Skip test files
        if "/3 Video Tests/" in path:
            skipped += 1
            continue

        filename = os.path.basename(path)
        name, year = extract_name_year(filename)

        if not name:
            print(f"  SKIP: Could not parse filename: {filename}")
            skipped += 1
            continue

        print(f"\n  [{item_id[:8]}] \"{detected_name}\" -> searching for \"{name}\" ({year})")

        # Search for the correct movie
        search_info = {"SearchInfo": {"Name": name}}
        if year:
            search_info["SearchInfo"]["Year"] = year

        results = api_post("/Items/RemoteSearch/Movie", search_info)

        if not results or len(results) == 0:
            print(f"    NO RESULTS found for \"{name}\" ({year})")
            failed += 1
            continue

        # Take the first result
        best = results[0]
        tmdb_id = best.get("ProviderIds", {}).get("Tmdb", "")
        result_name = best.get("Name", "?")
        result_year = best.get("ProductionYear", "?")

        print(f"    MATCH: \"{result_name}\" ({result_year}) TMDB={tmdb_id}")

        # Apply the identification
        try:
            apply_data = json.dumps({
                "ReplaceAllImages": True,
                "ReplaceAllMetadata": True,
                "SearchResult": best
            }).encode()
            req = urllib.request.Request(
                f"{JELLYFIN_URL}/Items/RemoteSearch/Apply/{item_id}?ReplaceAllImages=true&ReplaceAllMetadata=true",
                data=apply_data,
                headers=HEADERS,
                method="POST"
            )
            resp = urllib.request.urlopen(req)
            if resp.status in (200, 204):
                print(f"    APPLIED successfully")
                fixed += 1
            else:
                print(f"    APPLY returned status {resp.status}")
                failed += 1
        except Exception as e:
            print(f"    APPLY ERROR: {e}")
            failed += 1

        time.sleep(1)  # Be gentle with the API

    print(f"\n--- Summary ---")
    print(f"Fixed: {fixed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped} (test files or unparseable)")

if __name__ == "__main__":
    main()
