#!/usr/bin/env python3
"""
Pipeline B: Movie post-download processor
Watches /mnt/MovieAndTvShows/ToFix/ for .mkv files, queries TMDb to resolve
English title + franchise, then renames and routes to the correct library folder.

Usage:
  movieProcessor.py                    # process all .mkv in TOFIX_DIR
  movieProcessor.py FILE.mkv           # process a specific file
  movieProcessor.py --dry-run          # show routing without moving anything
  movieProcessor.py FILE.mkv --dry-run
"""

import os, sys, re, json, time, datetime, subprocess, logging, argparse
import urllib.request, urllib.parse

TOFIX_DIR     = "/mnt/MovieAndTvShows/ToFix/"
MOVIES_DIR    = "/mnt/MovieAndTvShows/Movies/"
SAGAS_DIR     = os.path.join(MOVIES_DIR, "1 Sagas")
QUARANTINE_DIR = os.path.join(TOFIX_DIR, "_quarantine")

# A top-level .mkv still present after a full run AND older than this many seconds
# is considered "stuck" (not an in-flight copy) and triggers a Telegram alert.
STUCK_FILE_AGE_SECS = 30 * 60

TMDB_TOKEN       = os.environ.get("TMDB_TOKEN", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# TMDb collection name keywords → Disney franchise subfolder name
# Keys are lowercase substrings matched against the collection name.
DISNEY_FRANCHISE_KEYWORDS = {
    "toy story":         "Toy Story",
    "cars":              "Cars",
    "finding nemo":      "Finding Nemo",
    "finding dory":      "Finding Nemo",
    "monsters, inc":     "Monster inc",
    "monsters university": "Monster inc",
    "incredibles":       "Incredibles",
    "frozen":            "Frozen",
    "wreck-it ralph":    "Wreck it Ralph",
    "ralph breaks":      "Wreck it Ralph",
    "zootopia":          "Zootopia",
    "moana":             "Moana",
    "aladdin":           "Aladin",      # intentional typo to match existing folder
    "jungle book":       "The Jungle Book",
    "lion king":         "The Lion King",
    "little mermaid":    "The Little Mermaid",
    "inside out":        "Inside out",
    "rescuers":          "The Rescuers",
    "fantasia":          "Fantasia",
    "lady and the tramp": "Lady and the Tramp",
}

# TMDb collection name keywords → DreamWorks franchise subfolder
DREAMWORKS_FRANCHISE_KEYWORDS = {
    "shrek":         "Shrek",
    "madagascar":    "Madagascar",
    "croods":        "Croods",
    "puss in boots": "Puss in the boots",
    "trolls":        "Trolls",
}

# Other animation studios with dedicated saga folders.
# Each entry: (substring_in_company_name, folder_name)
# Checked in order; first match wins.
STUDIO_FOLDER_MAP = [
    ("Illumination",          "Illumination"),
    ("Sony Pictures Animation", "Sony Animation"),
    ("Warner Animation Group",  "Warner Animation"),
    ("Studio Ghibli",           "Studio Ghibli"),
]


# ── HTTP helpers ────────────────────────────────────────────────────────────

def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ── TMDb ────────────────────────────────────────────────────────────────────

def tmdb_search(title, year):
    """Search TMDb for a movie; try Italian first, then English. Returns first result or None."""
    for lang in ("it", "en"):
        params = {"query": title, "language": lang}
        if year:
            params["primary_release_year"] = year
        url = "https://api.themoviedb.org/3/search/movie?" + urllib.parse.urlencode(params)
        data = _http_get(url, {"Authorization": f"Bearer {TMDB_TOKEN}"})
        results = data.get("results", [])
        if results:
            return results[0]
        # Retry without year constraint if no results
        if year:
            params.pop("primary_release_year")
            url = "https://api.themoviedb.org/3/search/movie?" + urllib.parse.urlencode(params)
            data = _http_get(url, {"Authorization": f"Bearer {TMDB_TOKEN}"})
            results = data.get("results", [])
            if results:
                return results[0]
    return None


def tmdb_details(movie_id):
    """Get full movie details including keywords (for Live Action detection)."""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?append_to_response=keywords"
    return _http_get(url, {"Authorization": f"Bearer {TMDB_TOKEN}"})


# ── Filename parser ─────────────────────────────────────────────────────────

def parse_filename(filename):
    """
    Parse JDownloader-style filename to (raw_title, year, quality).
    Input:  Scarlet.2025.iTA-JAP.Bluray.1080p.HEVC.HDR.x265-CYBER.mkv
    Output: ("Scarlet", "2025", "1080p")
    """
    stem = os.path.splitext(filename)[0]
    # Non-greedy title, then a dot-separated 4-digit year
    m = re.match(r'^(.+?)[\.\s](\d{4})[\.\s]', stem)
    if not m:
        return None, None, None

    raw_title = m.group(1).replace(".", " ").strip()
    year = m.group(2)

    sl = stem.lower()
    if "2160p" in sl or "uhd" in sl:
        quality = "4k"
    elif "1080p" in sl:
        quality = "1080p"
    else:
        quality = None

    return raw_title, year, quality


# ── Routing logic ───────────────────────────────────────────────────────────

def _words(s):
    """Lowercase significant words (stopwords removed, punctuation stripped)."""
    raw = set(re.sub(r"[^\w\s]", "", s.lower()).split())
    return raw - _STOPWORDS or raw  # fall back to raw if everything is a stopword


def _collection_keyword_match(collection_name, keyword_map):
    """Return folder name if any keyword map entry is a substring of collection_name."""
    cn = collection_name.lower()
    for keyword, folder in keyword_map.items():
        if keyword in cn:
            return folder
    return None


def _fuzzy_saga_match(collection_name, folder_names, threshold=0.5):
    """
    Word-overlap fuzzy match of collection_name against a list of folder names.
    Strips 'Collection / Saga / Series / Franchise' before matching.
    Returns (best_folder, score).
    """
    cleaned = re.sub(r"\b(collection|saga|series|franchise)\b", "", collection_name, flags=re.I).strip()
    c_words = _words(cleaned)
    if not c_words:
        return None, 0.0

    best, best_score = None, 0.0
    for folder in folder_names:
        f_words = _words(folder)
        if not f_words:
            continue
        overlap = len(c_words & f_words)
        score = overlap / max(len(c_words), len(f_words))
        if score > best_score:
            best, best_score = folder, score
    return best, best_score


# Folders that are "studio buckets" — not matched by collection fuzzy matching
_STUDIO_BUCKETS = frozenset(
    ["Disney", "DreamWorks", "Illumination", "Sony Animation",
     "Warner Animation", "Studio Ghibli", "Paramount"]
)

_STOPWORDS = frozenset(
    ["the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "but",
     "is", "it", "its", "this", "that"]
)


def get_destination(title_en, year, quality, details):
    """
    Returns (dest_path, confidence) where confidence is 'high' or 'low'.
    'low' means the file should go to quarantine for manual review.
    """
    companies = [c["name"] for c in details.get("production_companies", [])]
    collection = details.get("belongs_to_collection")
    keywords = [k["name"].lower() for k in details.get("keywords", {}).get("keywords", [])]

    q_suffix = f" - {quality}" if quality else ""
    fname = f"{title_en} ({year}){q_suffix}.mkv"

    is_disney = any("Disney" in c or "Pixar" in c for c in companies)
    # "DreamWorks Pictures" is a live-action studio; only "DreamWorks Animation"
    # and "DreamWorks SKG" hold the animated franchises in the saga folder.
    is_dreamworks = any(
        "DreamWorks" in c and "Pictures" not in c
        for c in companies
    )
    is_live_action = (
        any("live" in kw and ("action" in kw or "remake" in kw) for kw in keywords)
        or "remake" in keywords
    )

    # ── Disney / Pixar ───────────────────────────────────────────────────────
    if is_disney:
        if is_live_action:
            return os.path.join(SAGAS_DIR, "Disney", "Live Action", fname), "high"
        if collection:
            folder = _collection_keyword_match(collection["name"], DISNEY_FRANCHISE_KEYWORDS)
            if folder:
                return os.path.join(SAGAS_DIR, "Disney", folder, fname), "high"
        return os.path.join(SAGAS_DIR, "Disney", fname), "high"

    # ── Collection: try top-level saga folders first ─────────────────────────
    if collection:
        top_sagas = [
            d for d in os.listdir(SAGAS_DIR)
            if os.path.isdir(os.path.join(SAGAS_DIR, d)) and d not in _STUDIO_BUCKETS
        ]
        matched, score = _fuzzy_saga_match(collection["name"], top_sagas)
        if score >= 0.5:
            return os.path.join(SAGAS_DIR, matched, fname), "high"

        # DreamWorks: also check franchise subfolders
        if is_dreamworks:
            try:
                dw_subs = [
                    d for d in os.listdir(os.path.join(SAGAS_DIR, "DreamWorks"))
                    if os.path.isdir(os.path.join(SAGAS_DIR, "DreamWorks", d))
                ]
                folder = _collection_keyword_match(collection["name"], DREAMWORKS_FRANCHISE_KEYWORDS)
                if not folder:
                    folder_fuzzy, fscore = _fuzzy_saga_match(collection["name"], dw_subs)
                    if fscore >= 0.5:
                        folder = folder_fuzzy
                if folder:
                    return os.path.join(SAGAS_DIR, "DreamWorks", folder, fname), "high"
            except FileNotFoundError:
                pass

    # ── DreamWorks (no collection match above) ───────────────────────────────
    if is_dreamworks:
        return os.path.join(SAGAS_DIR, "DreamWorks", fname), "high"

    # ── Other animation studios ──────────────────────────────────────────────
    for studio_substr, folder_name in STUDIO_FOLDER_MAP:
        if any(studio_substr in c for c in companies):
            return os.path.join(SAGAS_DIR, folder_name, fname), "high"

    # ── Collection with no matching saga folder → quarantine ─────────────────
    if collection:
        return None, "low"

    # ── Standalone film ──────────────────────────────────────────────────────
    return os.path.join(MOVIES_DIR, fname), "high"


# ── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    body = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logging.warning(f"Telegram notify failed: {e}")


# ── Quarantine ──────────────────────────────────────────────────────────────

def quarantine_file(filepath, reason, message, dry_run=False, **extra):
    """
    Move a file that cannot be filed into _quarantine/ and drop a JSON sidecar
    (<filename>.quarantine.json) recording why. Returns False (never a success).

    Quarantining — rather than leaving the file in ToFix — is what keeps the
    level-triggered .path watcher from re-firing forever on an un-filable file
    (the old start-limit-hit jam). `extra` kwargs are merged into the sidecar.
    """
    filename = os.path.basename(filepath)
    if dry_run:
        print(f"  → QUARANTINE [{reason}] {message}")
        logging.warning(f"[DRY] would quarantine [{reason}]: {filename}")
        return False

    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    dest = os.path.join(QUARANTINE_DIR, filename)
    proc = subprocess.run(
        ["rsync", "-av", "--remove-source-files", filepath, dest],
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        # Could not even move to quarantine — surface it; the file stays put.
        err = f"❌ PipelineB: failed to quarantine <code>{filename}</code>:\n{proc.stderr[:300]}"
        logging.error(err)
        send_telegram(err)
        return False

    record = {
        "quarantined_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "reason": reason,
        "message": message,
        "original_filename": filename,
    }
    record.update(extra)
    try:
        with open(dest + ".quarantine.json", "w") as fh:
            json.dump(record, fh, indent=2, ensure_ascii=False)
    except OSError as e:
        logging.warning(f"Could not write quarantine sidecar for {filename}: {e}")

    notify = (
        f"🟡 PipelineB quarantined <code>{filename}</code>\n"
        f"reason: <b>{reason}</b>\n{message}"
    )
    logging.warning(notify)
    send_telegram(notify)
    return False


# ── File processor ──────────────────────────────────────────────────────────

def process_file(filepath, dry_run=False):
    filename = os.path.basename(filepath)
    prefix = "[DRY] " if dry_run else ""
    logging.info(f"{prefix}Processing: {filename}")

    raw_title, year, quality = parse_filename(filename)
    if not raw_title or not year:
        return quarantine_file(
            filepath,
            reason="unparseable_filename",
            message="Could not parse a title and 4-digit year from the filename.",
            dry_run=dry_run,
        )

    logging.info(f"  Parsed title='{raw_title}' year={year} quality={quality}")

    result = tmdb_search(raw_title, year)
    if not result:
        return quarantine_file(
            filepath,
            reason="tmdb_no_result",
            message=f"No TMDb match for parsed title '{raw_title}' ({year}).",
            dry_run=dry_run,
            parsed={"title": raw_title, "year": year, "quality": quality},
        )

    details = tmdb_details(result["id"])
    title_en = details.get("title", raw_title)
    actual_year = (details.get("release_date") or f"{year}-01-01")[:4]
    collection = details.get("belongs_to_collection")
    companies = [c["name"] for c in details.get("production_companies", [])]
    keywords = [k["name"] for k in details.get("keywords", {}).get("keywords", [])][:5]

    logging.info(
        f"  TMDb: '{title_en}' ({actual_year}) | "
        f"companies={companies[:3]} | "
        f"collection={collection['name'] if collection else None} | "
        f"keywords={keywords}"
    )

    dest, confidence = get_destination(title_en, actual_year, quality, details)

    if confidence == "low" or dest is None:
        collection_name = collection["name"] if collection else "none"
        return quarantine_file(
            filepath,
            reason="no_saga_folder",
            message=f"TMDb collection '{collection_name}' has no matching saga folder in '1 Sagas'.",
            dry_run=dry_run,
            parsed={"title": raw_title, "year": year, "quality": quality},
            tmdb={"title": title_en, "year": actual_year, "collection": collection_name},
        )

    dest_rel = dest.replace(MOVIES_DIR, "")

    # Check for an existing destination BEFORE the dry-run short-circuit so a dry
    # run also reports would-be duplicates instead of claiming a clean move.
    if os.path.exists(dest):
        return quarantine_file(
            filepath,
            reason="destination_exists",
            message=f"A file already exists at the destination: {dest_rel}",
            dry_run=dry_run,
            parsed={"title": raw_title, "year": year, "quality": quality},
            tmdb={"title": title_en, "year": actual_year},
            intended_destination=dest_rel,
        )

    if dry_run:
        print(f"  → {dest_rel}")
        return True

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    proc = subprocess.run(
        ["rsync", "-av", "--remove-source-files", filepath, dest],
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        return quarantine_file(
            filepath,
            reason="rsync_failed",
            message=f"rsync to the library failed: {proc.stderr[:300]}",
            dry_run=dry_run,
            parsed={"title": raw_title, "year": year, "quality": quality},
            tmdb={"title": title_en, "year": actual_year},
            intended_destination=dest_rel,
        )

    msg = (
        f"✅ PipelineB moved:\n"
        f"<code>{title_en} ({actual_year})</code>\n"
        f"→ <code>{dest_rel}</code>"
    )
    logging.info(msg)
    send_telegram(msg)
    return True


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Process .mkv files from ToFix/ into the media library.")
    parser.add_argument("file", nargs="?", help="Specific .mkv file to process (default: all in TOFIX_DIR)")
    parser.add_argument("--dry-run", action="store_true", help="Print proposed routing without moving files")
    args = parser.parse_args()

    if args.file:
        files = [args.file]
    else:
        try:
            files = [
                os.path.join(TOFIX_DIR, f)
                for f in os.listdir(TOFIX_DIR)
                if f.endswith(".mkv") and not f.startswith(".")
            ]
        except FileNotFoundError:
            logging.error(f"TOFIX_DIR not found: {TOFIX_DIR}")
            sys.exit(1)

    if not files:
        logging.info("No .mkv files to process.")
        return

    for f in sorted(files):
        process_file(f, dry_run=args.dry_run)

    # Watchdog: after a full real run every file should have been filed or
    # quarantined, so ToFix top-level should be empty. Anything still here and
    # older than STUCK_FILE_AGE_SECS (i.e. not a fresh in-flight copy) is stuck —
    # signal it instead of letting it silently sit / re-trigger the watcher.
    if not args.dry_run and not args.file:
        now = time.time()
        stuck = []
        for f in os.listdir(TOFIX_DIR):
            if not f.endswith(".mkv") or f.startswith("."):
                continue
            path = os.path.join(TOFIX_DIR, f)
            try:
                if now - os.path.getmtime(path) >= STUCK_FILE_AGE_SECS:
                    stuck.append(f)
            except OSError:
                continue
        if stuck:
            names = "\n".join(f"  • {x}" for x in sorted(stuck))
            alert = (
                f"⚠️ PipelineB: {len(stuck)} file(s) stuck in ToFix "
                f"(unprocessed &gt;{STUCK_FILE_AGE_SECS // 60}min):\n{names}"
            )
            logging.warning(alert)
            send_telegram(alert)


if __name__ == "__main__":
    main()
