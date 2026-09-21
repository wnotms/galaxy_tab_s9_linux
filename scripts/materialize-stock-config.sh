#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
parts_dir="$repo_root/reference/stock/config"
expected_raw=80693a069d406fbdafe01b73e65e8f1e15b681451bbb53b9d05fde7a93220112
expected_gzip=9a3a7f40efa79d6fecf6717cbb5f6273dc70d03b9c03de1f01115ab555befb33
dest=${1:-}

command -v base64 >/dev/null || { echo "base64 is required" >&2; exit 1; }
command -v gzip >/dev/null || { echo "gzip is required" >&2; exit 1; }

parts=(
  "$parts_dir/SM-X710-stock-5.15.153.config.gz.b64.part00"
  "$parts_dir/SM-X710-stock-5.15.153.config.gz.b64.part01"
  "$parts_dir/SM-X710-stock-5.15.153.config.gz.b64.part02"
  "$parts_dir/SM-X710-stock-5.15.153.config.gz.b64.part03"
  "$parts_dir/SM-X710-stock-5.15.153.config.gz.b64.part04"
)
for p in "${parts[@]}"; do
    [ -f "$p" ] || { echo "missing stock config part: $p" >&2; exit 1; }
done

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
archive="$tmpdir/stock.config.gz"
raw="$tmpdir/stock.config"

cat "${parts[@]}" | base64 -d > "$archive"
printf '%s  %s\n' "$expected_gzip" "$archive" | sha256sum -c - >/dev/null
gzip -dc "$archive" > "$raw"
printf '%s  %s\n' "$expected_raw" "$raw" | sha256sum -c - >/dev/null

if [ -n "$dest" ]; then
    install -m 0644 "$raw" "$dest"
    echo "materialized verified stock config: $dest"
else
    cat "$raw"
fi
