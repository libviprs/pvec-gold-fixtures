#!/usr/bin/env bash
# Refuse vendor artifacts, licence files and key-shaped strings (ADR 0007, docs/converters/archive.md).
#
#   tools/vendor_guard.sh --staged       the files staged for commit (the pre-commit hook)
#   tools/vendor_guard.sh --tree [DIR]   every file under DIR, default the repository (the CI check)
#
# The patterns live in tools/vendor-guard.patterns. The guard prints which file and which rule matched
# and never the matched text, so a refusal can't leak the thing it found. Exit 1 on any match.
set -u
here=$(cd "$(dirname "$0")" && pwd)
pat=$here/vendor-guard.patterns
mode=${1:---tree}
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT

case $mode in
  --staged)
    root=$(git rev-parse --show-toplevel) || exit 2
    git diff --cached --name-only --diff-filter=ACMR -z > "$tmp" ;;
  --tree)
    root=$(cd "${2:-$here/..}" && pwd)
    if git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 && [ "$(git -C "$root" rev-parse --show-toplevel)" = "$root" ]; then
      git -C "$root" ls-files -co --exclude-standard -z > "$tmp"
    else
      (cd "$root" && find . -type f -not -path './.git/*' -not -name '*.pyc' -not -path '*/__pycache__/*' -print0 | sed -z 's|^\./||') > "$tmp"
    fi ;;
  *) sed -n '2,8p' "$0" >&2; exit 2 ;;
esac

# files whose job is to spell the patterns out (or to plant a canary) are not scanned for content
skip_content='^(tools/vendor-guard\.patterns|docs/converters/archive\.md|tests/test_vendor_guard\.py|tests/test_convert_wrapper\.py|tests/test_corpus\.py)$'
bad=0
while IFS= read -r -d '' f; do
  [ -n "$f" ] || continue
  base=${f##*/}
  while read -r kind p; do
    case $kind in
      path-prefix) case $f in "$p"*) echo "REFUSED path-prefix '$p': $f"; bad=1 ;; esac ;;
      path-glob) case $base in $p) echo "REFUSED path-glob '$p': $f"; bad=1 ;; esac ;;
    esac
  done < <(grep -v -e '^#' -e '^$' "$pat" | grep -e '^path-')
  [ -f "$root/$f" ] || continue
  if ! printf '%s' "$f" | grep -Eq "$skip_content"; then
    while read -r kind p; do
      [ "$kind" = content-regex ] || continue
      n=$(grep -IEic -e "$p" "$root/$f" 2>/dev/null || true)
      if [ "${n:-0}" -gt 0 ]; then echo "REFUSED content-regex '$p': $f ($n line(s))"; bad=1; fi
    done < <(grep -v -e '^#' -e '^$' "$pat")
  fi
done < "$tmp"
[ "$bad" -eq 0 ] && echo "vendor_guard: clean"
exit "$bad"
