#!/usr/bin/env python3
"""Create .nfo files for Jellyfin movies in saga/anime/sd folders."""
import json
import os
import urllib.request

URL = "http://localhost:8096"
TOKEN = "e8202ef323524fd1acb11898fabb1869"
HEADERS = {"X-Emby-Token": TOKEN}

# Map container paths to host paths
# Inside container: /data/movies -> host: /mnt/MovieAndTvShows/Movies
PATH_MAP = "/data/movies"
HOST_MAP = "/mnt/MovieAndTvShows/Movies"

def main():
    req = urllib.request.Request(
        f"{URL}/Items?Recursive=true&IncludeItemTypes=Movie&Fields=Path,ProviderIds&Limit=1000",
        headers=HEADERS
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())

    created = 0
    skipped = 0

    for item in data.get("Items", []):
        path = item.get("Path", "")
        tmdb = item.get("ProviderIds", {}).get("Tmdb", "")
        imdb = item.get("ProviderIds", {}).get("Imdb", "")
        name = item.get("Name", "")
        year = item.get("ProductionYear", "")

        if not tmdb or not path:
            continue

        # Only for saga/anime/sd folders
        if not any(x in path for x in ["/1 Sagas/", "/2 Anime/", "/5 SD Movies/"]):
            continue

        # Convert container path to host path
        host_path = path.replace(PATH_MAP, HOST_MAP)

        # NFO file goes next to the movie file, same name but .nfo extension
        nfo_path = os.path.splitext(host_path)[0] + ".nfo"

        if os.path.exists(nfo_path):
            skipped += 1
            continue

        nfo_content = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'
        nfo_content += "<movie>\n"
        nfo_content += f"  <title>{name}</title>\n"
        if year:
            nfo_content += f"  <year>{year}</year>\n"
        if tmdb:
            nfo_content += f"  <tmdbid>{tmdb}</tmdbid>\n"
        if imdb:
            nfo_content += f"  <imdbid>{imdb}</imdbid>\n"
        nfo_content += "</movie>\n"

        try:
            with open(nfo_path, "w", encoding="utf-8") as f:
                f.write(nfo_content)
            created += 1
            print(f"  Created: {nfo_path}")
        except Exception as e:
            print(f"  ERROR: {nfo_path}: {e}")

    print(f"\nDone! Created: {created}, Skipped (already exists): {skipped}")

if __name__ == "__main__":
    main()
