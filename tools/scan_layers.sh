#!/bin/bash
# Runs inside a container: reads a `docker save` tar on stdin, unpacks every layer, and scans the
# files, the image history text and any log files for licence material. Prints where, which pattern
# and how many lines (or which file inside a layer), never the matched text. Exit 1 on any match not
# covered by tools/licence-allowlist.txt. Driven by tools/check_no_licence.sh.
#   scan_layers.sh HISTORY_FILE [LOGFILE...] < image.tar
# CANARY_PATTERN in the environment adds a pattern, to prove the check fires.
set -u
hist=$1; shift
here=$(cd "$(dirname "$0")" && pwd)
declare -A PAT
PAT[private-key-ml]='-----BEGIN [A-Z ]*PRIVATE KEY-----\r?\n[A-Za-z0-9+/=]{40,}'
PAT[licence-assignment]='(licen[cs]e|activation|serial|product)[_ -]?(key|code|token)["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9+/_=-]{16,}'
[ -n "${CANARY_PATTERN:-}" ] && PAT[canary]=$CANARY_PATTERN
allowed() { # pattern-name, path
  local n g
  while read -r n g _; do
    case $n in ''|'#'*) continue ;; esac
    [ "$n" = "$1" ] || continue
    # shellcheck disable=SC2254
    case $2 in $g) return 0 ;; esac
  done < "$here/licence-allowlist.txt"
  return 1
}
grep_files() { # name, dir -> file list on stdout
  case $1 in
    *-ml) grep -r -l -a -z -P -e "${PAT[$1]}" "$2" 2>/dev/null ;;
    *) grep -r -l -a -E -i -e "${PAT[$1]}" "$2" 2>/dev/null ;;
  esac
}
scan_file() { # where, file
  local name n
  for name in "${!PAT[@]}"; do
    case $name in
      *-ml) n=$(grep -a -z -c -P -e "${PAT[$name]}" "$2") ;;
      *) n=$(grep -a -c -E -i -e "${PAT[$name]}" "$2") ;;
    esac
    [ "${n:-0}" -gt 0 ] && echo "MATCH $1: $n line(s) for pattern '$name'"
  done
}
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
mkdir "$t/save"; tar -x -C "$t/save"
{
  scan_file "image history" "$hist"
  find "$t/save" -type f | sort | while read -r blob; do
    rel=${blob#$t/save/}
    if [ "$(head -c2 "$blob" | od -An -tx1 | tr -d ' ')" = "1f8b" ]; then gunzip -c "$blob" > "$t/b.tar" 2>/dev/null; else cp "$blob" "$t/b.tar"; fi
    rm -rf "$t/x"; mkdir "$t/x"
    if tar -tf "$t/b.tar" >/dev/null 2>&1; then
      tar -xf "$t/b.tar" -C "$t/x" 2>/dev/null
      for name in "${!PAT[@]}"; do
        grep_files "$name" "$t/x" | while read -r f; do
          p=/${f#$t/x/}
          allowed "$name" "$p" || echo "MATCH layer $rel: file $p, pattern '$name'"
        done
      done
    else
      scan_file "image file $rel" "$t/b.tar"
    fi
  done
  for f in "$@"; do scan_file "log $f" "$f"; done
} > "$t/report.txt"
cat "$t/report.txt"
if [ -s "$t/report.txt" ]; then exit 1; fi
echo "no licence material found (history, every layer file$([ $# -gt 0 ] && echo ', logs'))"
