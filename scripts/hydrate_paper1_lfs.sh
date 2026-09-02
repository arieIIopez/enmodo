#!/usr/bin/env bash
set -euo pipefail

# Selectively hydrate the canonical Git LFS inputs for Paper I without pulling
# every large object stored in ENMODO. Run from any location inside the repo:
#
#   bash scripts/hydrate_paper1_lfs.sh
#   bash scripts/hydrate_paper1_lfs.sh --with-bogota-2019
#
# The script verifies both byte size and SHA-256 (the Git LFS oid) after pull.

WITH_BOGOTA_2019=0
for arg in "$@"; do
  case "$arg" in
    --with-bogota-2019) WITH_BOGOTA_2019=1 ;;
    -h|--help)
      sed -n '1,18p' "$0"
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

MEXICO="ciudad-de-mexico/viajes_personas_mexico_2017.csv"
SANTIAGO="santiago/csv/viajes_personas_santiago_2012.csv"
BOGOTA15="bogota/2015/output-csv/viajes_personas_bogota_2015.csv"
BOGOTA19="bogota/2019/csv/viajes_personas_bogota_2019.csv"

OID["$MEXICO"]="f84c1162c12408889f4ea9175e95e9f9bdad756d4ab4d3d03c68b31658a7a95c"
SIZE["$MEXICO"]="132263428"
OID["$SANTIAGO"]="33acc8744cde019b2a47abe9e120a14253658733da57494598e0a92a5575f169"
SIZE["$SANTIAGO"]="36704476"
OID["$BOGOTA15"]="4a43428f72b1e963d116083d366cfcaeb673ba4b338f21109f340525b35ad90a"
SIZE["$BOGOTA15"]="55449326"
OID["$BOGOTA19"]="0bb99370ab46496d97f0b1f217e6d5cd446efff1467e1bfbf90d4274c513cef8"
SIZE["$BOGOTA19"]="54901849"

FILES=("$MEXICO" "$SANTIAGO" "$BOGOTA15")
if [[ "$WITH_BOGOTA_2019" -eq 1 ]]; then
  FILES+=("$BOGOTA19")
fi

INCLUDE="$(IFS=,; echo "${FILES[*]}")"
echo "Hydrating canonical Paper I LFS objects:"
printf '  - %s\n' "${FILES[@]}"

git lfs pull --include="$INCLUDE" --exclude=""

echo

echo "Verifying content..."
for path in "${FILES[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "MISSING: $path" >&2
    exit 1
  fi

  if head -n 1 "$path" | grep -q '^version https://git-lfs.github.com/spec/v1$'; then
    echo "NOT HYDRATED: $path is still an LFS pointer" >&2
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
echo "Paper I LFS inputs hydrated and verified."
echo "Next: audit schemas before constructing person-day records."
