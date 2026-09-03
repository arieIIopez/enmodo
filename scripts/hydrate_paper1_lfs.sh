#!/usr/bin/env bash
set -euo pipefail

# Selectively hydrate the canonical Git LFS inputs for Paper I without pulling
# every large object stored in ENMODO. Run from any location inside the repo:
#
#   bash scripts/hydrate_paper1_lfs.sh
#   bash scripts/hydrate_paper1_lfs.sh --with-bogota-2019
#
# PROVENANCE AND RECOVERY STRATEGY
# --------------------------------
# arieIIopez/enmodo and the original RacoFernandez/enmodo repository retain the
# canonical Git LFS pointer files, but their GitHub LFS backends currently
# return HTTP 410 for the historical binary objects. Because Git LFS object IDs
# are SHA-256 content hashes, an identical object recovered from another
# historical fork is byte-for-byte the same dataset.
#
# This script therefore probes an explicit, versioned list of ENMODO forks that
# contain the same pointers. It accepts data only after verifying every file by
# the frozen SHA-256 OID and byte size. The code/history source remains
# arieIIopez/enmodo; the binary storage endpoint is treated purely as a content-
# addressed recovery source.
#
# Bogotá 2015 personas.xlsx is a regular Git blob and is verified separately.

WITH_BOGOTA_2019=0
for arg in "$@"; do
  case "$arg" in
    --with-bogota-2019) WITH_BOGOTA_2019=1 ;;
    -h|--help)
      sed -n '1,36p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo "Run this script inside a clone of arieIIopez/enmodo" >&2
  exit 1
fi
cd "$ROOT"

if ! git lfs version >/dev/null 2>&1; then
  cat >&2 <<'EOF'
git-lfs is required.
On Ubuntu/Debian:
  sudo apt update
  sudo apt install git-lfs
  git lfs install
EOF
  exit 1
fi

git lfs install --local >/dev/null

declare -A OID
declare -A SIZE

MEXICO_TRIPS="ciudad-de-mexico/viajes_personas_mexico_2017.csv"
MEXICO_PERSONS="ciudad-de-mexico/source-csv/tsdem.csv"
SANTIAGO_TRIPS="santiago/csv/viajes_personas_santiago_2012.csv"
SANTIAGO_PERSONS="santiago/source-csv/personas.csv"
BOGOTA15_TRIPS="bogota/2015/output-csv/viajes_personas_bogota_2015.csv"
BOGOTA15_PERSONS="bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx"
BOGOTA19_TRIPS="bogota/2019/csv/viajes_personas_bogota_2019.csv"

OID["$MEXICO_TRIPS"]="f84c1162c12408889f4ea9175e95e9f9bdad756d4ab4d3d03c68b31658a7a95c"
SIZE["$MEXICO_TRIPS"]="132263428"
OID["$MEXICO_PERSONS"]="1b739929ef0207251c835870e29376a1066b53253b4b879f1f330c2622d8ce93"
SIZE["$MEXICO_PERSONS"]="22649303"
OID["$SANTIAGO_TRIPS"]="33acc8744cde019b2a47abe9e120a14253658733da57494598e0a92a5575f169"
SIZE["$SANTIAGO_TRIPS"]="36704476"
OID["$SANTIAGO_PERSONS"]="57a5ae5631cc0a9ab61aa86ab48524b06f6a6c507cb3c696f23fe7d568b454fa"
SIZE["$SANTIAGO_PERSONS"]="6862309"
OID["$BOGOTA15_TRIPS"]="4a43428f72b1e963d116083d366cfcaeb673ba4b338f21109f340525b35ad90a"
SIZE["$BOGOTA15_TRIPS"]="55449326"
OID["$BOGOTA19_TRIPS"]="0bb99370ab46496d97f0b1f217e6d5cd446efff1467e1bfbf90d4274c513cef8"
SIZE["$BOGOTA19_TRIPS"]="54901849"

LFS_FILES=(
  "$MEXICO_TRIPS"
  "$MEXICO_PERSONS"
  "$SANTIAGO_TRIPS"
  "$SANTIAGO_PERSONS"
  "$BOGOTA15_TRIPS"
)
if [[ "$WITH_BOGOTA_2019" -eq 1 ]]; then
  LFS_FILES+=("$BOGOTA19_TRIPS")
fi

INCLUDE="$(IFS=,; echo "${LFS_FILES[*]}")"

# Historical forks are ordered by provenance/age. Recovery can accumulate
# objects across sources: after each fetch we checkout whatever has become
# available locally, then continue only for still-missing objects.
RECOVERY_SOURCES=(
  "source-original|https://github.com/RacoFernandez/enmodo.git|main"
  "source-eugenrb|https://github.com/eugenrb/enmodo.git|main"
  "source-freddy|https://github.com/2020freddyoscar2021/enmodo.git|main"
)

ensure_remote() {
  local name="$1" url="$2"
  if git remote get-url "$name" >/dev/null 2>&1; then
    local existing
    existing="$(git remote get-url "$name")"
    if [[ "$existing" != "$url" ]]; then
      echo "Remote $name exists with unexpected URL" >&2
      echo "  expected $url" >&2
      echo "  actual   $existing" >&2
      exit 1
    fi
  else
    git remote add "$name" "$url"
  fi
}

all_hydrated() {
  local path
  for path in "${LFS_FILES[@]}"; do
    [[ -f "$path" ]] || return 1
    if head -n 1 "$path" | grep -q '^version https://git-lfs.github.com/spec/v1$'; then
      return 1
    fi
  done
  return 0
}

echo "Canonical Paper I LFS objects requested:"
printf '  - %s\n' "${LFS_FILES[@]}"

echo
for source in "${RECOVERY_SOURCES[@]}"; do
  IFS='|' read -r remote_name remote_url remote_ref <<<"$source"
  ensure_remote "$remote_name" "$remote_url"
  echo "Trying LFS recovery source: $remote_url"

  # A remote may contain only a subset. Do not abort on fetch failure; objects
  # successfully transferred before the error remain in the local LFS store.
  set +e
  git lfs fetch "$remote_name" "$remote_ref" --include="$INCLUDE" --exclude=""
  fetch_status=$?
  set -e
  echo "  fetch exit status: $fetch_status"

  git lfs checkout "${LFS_FILES[@]}" >/dev/null 2>&1 || true
  if all_hydrated; then
    echo "All requested LFS objects recovered after source: $remote_url"
    break
  fi
  echo "  some requested objects remain unavailable; continuing"
done

echo

echo "Verifying LFS content..."
for path in "${LFS_FILES[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "MISSING: $path" >&2
    exit 1
  fi

  if head -n 1 "$path" | grep -q '^version https://git-lfs.github.com/spec/v1$'; then
    echo "NOT HYDRATED AFTER ALL RECOVERY SOURCES: $path" >&2
    echo "  expected oid sha256:${OID[$path]}" >&2
    exit 1
  fi

  actual_size="$(stat -c '%s' "$path")"
  actual_oid="$(sha256sum "$path" | awk '{print $1}')"

  if [[ "$actual_size" != "${SIZE[$path]}" ]]; then
    echo "SIZE MISMATCH: $path" >&2
    echo "  expected ${SIZE[$path]} bytes" >&2
    echo "  actual   $actual_size bytes" >&2
    exit 1
  fi

  if [[ "$actual_oid" != "${OID[$path]}" ]]; then
    echo "SHA-256 MISMATCH: $path" >&2
    echo "  expected ${OID[$path]}" >&2
    echo "  actual   $actual_oid" >&2
    exit 1
  fi

  echo "OK  $path"
done

echo

echo "Verifying Bogotá 2015 person universe (regular Git blob)..."
if [[ ! -f "$BOGOTA15_PERSONS" ]]; then
  echo "MISSING: $BOGOTA15_PERSONS" >&2
  exit 1
fi
bog_size="$(stat -c '%s' "$BOGOTA15_PERSONS")"
bog_blob="$(git hash-object "$BOGOTA15_PERSONS")"
if [[ "$bog_size" != "24555372" ]]; then
  echo "SIZE MISMATCH: $BOGOTA15_PERSONS" >&2
  echo "  expected 24555372 bytes" >&2
  echo "  actual   $bog_size bytes" >&2
  exit 1
fi
if [[ "$bog_blob" != "252a4d99434ede490f0c9b2670bddfb25178f093" ]]; then
  echo "GIT BLOB MISMATCH: $BOGOTA15_PERSONS" >&2
  echo "  expected 252a4d99434ede490f0c9b2670bddfb25178f093" >&2
  echo "  actual   $bog_blob" >&2
  exit 1
fi
echo "OK  $BOGOTA15_PERSONS"

echo
echo "Paper I inputs hydrated and verified byte-for-byte."
echo "Code source: arieIIopez/enmodo; LFS recovery is content-addressed by frozen OID."
echo "Next: reconstruct person-days and evaluate the preregistered support rule."
