#!/usr/bin/env bash
# find_missing_or_duplicated.sh
# Compare every file in <original_dir> (by content hash) against one or more
# other directories, reporting per file whether it is DUPLICATED (and where)
# or MISSING (exists only in the original).
#
# Hashes can be cached to disk (--cache FILE) so an interrupted run resumes:
# only new or changed files (by size/mtime) get re-hashed.
#
# Usage:
#   find_missing_or_duplicated.sh [--format text|json] [--summary]
#                                 [--cache FILE] [--resume]
#                                 <original_dir> <other_dir1> [other_dir2] ...

set -euo pipefail

FORMAT="text"; SHOW_SUMMARY=0; CACHE_FILE=""; RESUME=0

POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --format)  FORMAT="${2:-}"; shift 2 ;;
        --json)    FORMAT="json";   shift ;;
        --summary) SHOW_SUMMARY=1;  shift ;;
        --cache)   CACHE_FILE="${2:-}"; shift 2 ;;
        --resume)  RESUME=1;        shift ;;
        -h|--help) grep '^#' "$0" | sed 's/^#\{1,\} \{0,1\}//'; exit 0 ;;
        --) shift; POSITIONAL+=("$@"); break ;;
        -*) echo "Unknown option: $1" >&2; exit 1 ;;
        *)  POSITIONAL+=("$1"); shift ;;
    esac
done
set -- "${POSITIONAL[@]}"

[[ "$FORMAT" == "text" || "$FORMAT" == "json" ]] || { echo "Error: --format must be text|json" >&2; exit 1; }
if [[ "$FORMAT" == "json" ]] && ! command -v jq >/dev/null 2>&1; then
    echo "Error: 'jq' is required for JSON output (sudo apt install jq)" >&2; exit 1
fi
if [[ "$RESUME" -eq 1 ]]; then
    [[ -n "$CACHE_FILE" ]] || { echo "Error: --resume requires --cache FILE" >&2; exit 1; }
    [[ -f "$CACHE_FILE" ]] || { echo "Error: --resume: cache '$CACHE_FILE' not found" >&2; exit 1; }
fi
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 [--format text|json] [--summary] [--cache FILE] [--resume] <original_dir> <other_dir1> ..." >&2
    exit 1
fi

ORIGINAL="$1"; shift
OTHER_DIRS=("$@")
for d in "$ORIGINAL" "${OTHER_DIRS[@]}"; do
    [[ -d "$d" ]] || { echo "Error: directory '$d' does not exist" >&2; exit 1; }
done

# ---- hash cache ------------------------------------------------------------
declare -A CACHE            # path -> "hash\tsize\tmtime"
HASH_RESULT=""

load_cache() {
    [[ -n "$CACHE_FILE" && -f "$CACHE_FILE" ]] || return 0
    local hash size mtime path n=0
    while IFS=$'\t' read -r hash size mtime path; do
        [[ -z "${hash:-}" || -z "${path:-}" ]] && continue
        CACHE["$path"]="$hash"$'\t'"$size"$'\t'"$mtime"; n=$((n+1))
    done < "$CACHE_FILE"
    echo "Loaded $n cached hash(es) from '$CACHE_FILE'" >&2
}

# hash_one <path> <size> <mtime> -> sets HASH_RESULT ; returns 1 if unreadable
hash_one() {
    local path="$1" size="$2" mtime="$3" cached c_hash c_size c_mtime
    cached="${CACHE[$path]:-}"
    if [[ -n "$cached" ]]; then
        IFS=$'\t' read -r c_hash c_size c_mtime <<< "$cached"
        if [[ "$c_size" == "$size" && "$c_mtime" == "$mtime" ]]; then
            HASH_RESULT="$c_hash"; return 0        # cache hit -> skip hashing
        fi
    fi
    if ! HASH_RESULT="$(sha256sum -- "$path" 2>/dev/null | awk '{print $1}')" \
         || [[ -z "$HASH_RESULT" ]]; then
        echo "  WARN: cannot read '$path', skipping" >&2; return 1
    fi
    CACHE["$path"]="$HASH_RESULT"$'\t'"$size"$'\t'"$mtime"
    [[ -n "$CACHE_FILE" ]] && \
        printf '%s\t%s\t%s\t%s\n' "$HASH_RESULT" "$size" "$mtime" "$path" >> "$CACHE_FILE"
    return 0
}

load_cache

# ---- phase 1: index the other directories ---------------------------------
declare -A HASH_TO_FILES    # hash -> "dir\tpath\n" (repeatable)
echo "Indexing ${#OTHER_DIRS[@]} directory(ies)..." >&2
for dir in "${OTHER_DIRS[@]}"; do
    echo "  Scanning '$dir'..." >&2
    while IFS=$'\t' read -r -d '' size mtime path; do
        hash_one "$path" "$size" "$mtime" || continue
        HASH_TO_FILES["$HASH_RESULT"]+="${dir}"$'\t'"${path}"$'\n'
    done < <(find "$dir" -type f -printf '%s\t%T@\t%p\0')
done

# ---- phase 2: hash original and compare -----------------------------------
echo "Scanning '$ORIGINAL' and comparing..." >&2
R_FILE=(); R_HASH=(); R_STATUS=(); R_MATCHES=()
dup_count=0; miss_count=0; total=0
while IFS=$'\t' read -r -d '' size mtime path; do
    hash_one "$path" "$size" "$mtime" || continue
    total=$((total+1))
    matches="${HASH_TO_FILES[$HASH_RESULT]:-}"
    if [[ -n "$matches" ]]; then status="duplicated"; dup_count=$((dup_count+1))
    else                        status="missing";    miss_count=$((miss_count+1)); fi
    R_FILE+=("$path"); R_HASH+=("$HASH_RESULT"); R_STATUS+=("$status"); R_MATCHES+=("$matches")
done < <(find "$ORIGINAL" -type f -printf '%s\t%T@\t%p\0')

# ---- phase 3: render -------------------------------------------------------
render_text() {
    echo "---"
    for i in "${!R_FILE[@]}"; do
        if [[ "${R_STATUS[$i]}" == "duplicated" ]]; then
            echo "DUPLICATED: ${R_FILE[$i]}"
            while IFS=$'\t' read -r dlabel dpath; do
                [[ -z "$dlabel" ]] && continue
                echo "  -> found in [$dlabel]: $dpath"
            done <<< "${R_MATCHES[$i]}"
        else
            echo "MISSING:    ${R_FILE[$i]}"
        fi
    done
    [[ "$SHOW_SUMMARY" -eq 1 ]] && { echo "---"; echo "Total: $total | Duplicated: $dup_count | Missing: $miss_count"; }
    return 0
}

render_json() {
    local objects=() i
    for i in "${!R_FILE[@]}"; do
        objects+=("$(jq -c -n \
            --arg file "${R_FILE[$i]}" --arg hash "${R_HASH[$i]}" \
            --arg status "${R_STATUS[$i]}" --arg matches "${R_MATCHES[$i]}" \
            '{ file:$file, hash:$hash, status:$status,
               found_in: ($matches | split("\n") | map(select(length>0))
                          | map( index("\t") as $t | { directory:.[0:$t], path:.[($t+1):] } )) }')")
    done
    local dirs_json
    dirs_json=$(printf '%s\n' "${OTHER_DIRS[@]}" | jq -R -s 'split("\n")|map(select(length>0))')
    jq -n --arg original "$ORIGINAL" --argjson dirs "$dirs_json" \
        --argjson total "$total" --argjson dup "$dup_count" --argjson miss "$miss_count" \
        --slurpfile results <(printf '%s\n' "${objects[@]}") \
        '{ original:$original, checked_directories:$dirs,
           summary:{total:$total,duplicated:$dup,missing:$miss}, results:$results }'
}

case "$FORMAT" in text) render_text ;; json) render_json ;; esac
