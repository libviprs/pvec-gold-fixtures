#!/usr/bin/env bash
# In-image entrypoint of cadex-converter: source.dwg -> primary.step (STEP AP242).
#
#   convert_cadex.sh --in source.dwg --out primary.step [--status primary.status.json]
#
# Writes one status record (schema/converter-status.schema.json) every run, ok or not. The output
# is produced under a temporary name and moved into place only after it passes the checks below,
# so a failed run leaves no primary.step, not even a stale one from an earlier run.
#
# Exit codes (shared with the ODA converter):
#   0 ok  10 bad arguments  11 input missing/unreadable  12 input malformed  13 DWG version unsupported
#   14 licence/activation unavailable  15 conversion failed  16 output not produced  17 declared schema not AP242
#   20 internal error
#
# The only line that knows the vendor's command line is in $CADEX_VENDOR_CMD, a small script the
# image build installs next to the vendor artifact (docker/cadex/Dockerfile). Its contract:
#   $CADEX_VENDOR_CMD <in.dwg> <out.step>   exit 0 on success, otherwise one of 11..16 above
#                                            (anything else is treated as 15), diagnostics on stderr
#   $CADEX_VERSION_CMD                      prints the product build version on one line
# No licence or key is read, printed or logged here: the vendor command finds its licence at the
# path mounted at run time (see docker-compose.yml), and this script never opens that path.
set -u

VENDOR_CMD=${CADEX_VENDOR_CMD:-/opt/cadex/bin/convert-cmd}
VERSION_CMD=${CADEX_VERSION_CMD:-/opt/cadex/bin/product-version}
PRODUCT_NAME=${CADEX_PRODUCT_NAME:-CAD Exchanger Batch}

in=""; out=""; status=""
while [ $# -gt 0 ]; do
  case $1 in
    --in) in=${2:-}; shift 2 ;;
    --out) out=${2:-}; shift 2 ;;
    --status) status=${2:-}; shift 2 ;;
    *) in=""; shift ;;
  esac
done
[ -n "$status" ] || status="${out%.step}.status.json"

now() { date +%s.%N; }
start=$(now)
warnings=()
code=0; klass=""; message=""; declared=""; out_sha=""; in_sha=""
version="unknown"

jesc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n\r\t' '   '; }

write_status() {
  local end elapsed w=""
  end=$(now)
  elapsed=$(awk -v a="$start" -v b="$end" 'BEGIN{printf "%.3f", b-a}')
  for x in "${warnings[@]+"${warnings[@]}"}"; do w="$w${w:+, }\"$(jesc "$x")\""; done
  local st="OK" err="null" outj="null" insha="null" decl="null"
  if [ "$code" -ne 0 ]; then st="ERROR"; err="{\"code\": $code, \"class\": \"$klass\", \"message\": \"$(jesc "$message")\"}"; fi
  [ -n "$in_sha" ] && insha="\"$in_sha\""
  [ -n "$declared" ] && decl="\"$(jesc "$declared")\""
  [ "$code" -eq 0 ] && outj="{\"path\": \"$(jesc "$out")\", \"sha256\": \"$out_sha\"}"
  mkdir -p "$(dirname "$status")" 2>/dev/null
  printf '{\n  "schema_version": "pvec-gold/converter-status/1",\n  "converter": "cadex",\n  "status": "%s",\n  "exit_code": %d,\n  "input": {"path": "%s", "sha256": %s},\n  "output": %s,\n  "product": {"name": "%s", "version": "%s"},\n  "declared_schema": %s,\n  "wall_time_seconds": "%s",\n  "warnings": [%s],\n  "error": %s\n}\n' \
    "$st" "$code" "$(jesc "$in")" "$insha" "$outj" "$(jesc "$PRODUCT_NAME")" "$(jesc "$version")" "$decl" "$elapsed" "$w" "$err" > "$status"
}

fail() { code=$1; klass=$2; message=$3; write_status; exit "$code"; }

[ -n "$in" ] && [ -n "$out" ] || { in=${in:-}; out=${out:-unset.step}; status=${status:-unset.status.json}; fail 10 BAD_ARGUMENTS "usage: convert_cadex.sh --in source.dwg --out primary.step [--status file]"; }

rm -f "$out"   # never leave a stale output behind a failed run
[ -r "$in" ] && [ -f "$in" ] || fail 11 INPUT_UNREADABLE "cannot read input"
in_sha=$(sha256sum "$in" | cut -d' ' -f1)
version=$("$VERSION_CMD" 2>/dev/null | head -n1) || version="unknown"
[ -n "$version" ] || version="unknown"

tmp="${out}.partial.$$"
trap 'rm -f "$tmp"' EXIT
errlog=$(mktemp)
"$VENDOR_CMD" "$in" "$tmp" 2>"$errlog"
rc=$?
if [ $rc -ne 0 ]; then
  case $rc in
    11) klass=INPUT_UNREADABLE ;; 12) klass=INPUT_MALFORMED ;; 13) klass=DWG_VERSION_UNSUPPORTED ;;
    14) klass=LICENCE_UNAVAILABLE ;; 16) klass=OUTPUT_NOT_WRITTEN ;; *) rc=15; klass=CONVERSION_FAILED ;;
  esac
  msg=$(head -c 400 "$errlog"); rm -f "$errlog"
  fail "$rc" "$klass" "${msg:-converter exited non-zero}"
fi
rm -f "$errlog"

[ -s "$tmp" ] || fail 16 OUTPUT_NOT_WRITTEN "converter reported success but wrote no output"
head -c 20 "$tmp" | grep -q '^ISO-10303-21;' || fail 16 OUTPUT_NOT_WRITTEN "output is not a STEP Part 21 file"
declared=$(tr '\n\r' '  ' < "$tmp" | grep -o "FILE_SCHEMA *( *( *'[^']*'" | head -n1 | sed "s/.*'\\(.*\\)'/\\1/")
case $declared in
  *AP242*|*ap242*|*"10303 442"*) : ;;
  *) fail 17 SCHEMA_NOT_AP242 "declared schema is '${declared:-none}', not AP242" ;;
esac
mv "$tmp" "$out" || fail 16 OUTPUT_NOT_WRITTEN "could not move output into place"
out_sha=$(sha256sum "$out" | cut -d' ' -f1)
write_status
exit 0
