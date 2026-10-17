#!/usr/bin/env bash
# The converter Dockerfiles must fail loudly, and with a message that names the problem, when the
# vendor artifact is absent, unpinned or the wrong file, and must never fall back to anything else.
# The last case, a correct pin on a dummy file, proves the build gets as far as the install step,
# which is the placeholder that needs the real artifact. The dummy file is not vendor software.
#
#   tools/check_converter_images.sh
#
# The tree is pushed to the x86_64 build host (MARS), the builds run there with `docker build`, and
# the scratch tree is removed at the end. Nothing is executed on this machine but ssh and docker.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
nas=$here/../tools/nas.sh; [ -x "$nas" ] || nas=${NAS_SH:-/Users/rom/workspace/libviprs/tools/nas.sh}
host=${NAS:-devshell@192.168.0.100}
name=gold-conv-$(basename "$here")
ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR "$host")
dir=/work/nas-work/$name
trap '"$nas" clean "$name" >/dev/null' EXIT
"$nas" push "$here" "$name" >/dev/null
"$nas" run "$name" python:3.12-slim 'rm -rf vendor; mkdir -p vendor/cadex vendor/oda; printf "not a vendor artifact" > vendor/cadex/dummy.bin; cp vendor/cadex/dummy.bin vendor/oda/dummy-a.bin; cp vendor/cadex/dummy.bin vendor/oda/dummy-b.bin'
good=$(printf 'not a vendor artifact' | shasum -a 256 | cut -d' ' -f1)
bad=0000000000000000000000000000000000000000000000000000000000000000
rc_all=0
expect_fail() { # name, pattern, docker build args...
  local n=$1 pat=$2; shift 2
  local out rc
  out=$("${ssh[@]}" "cd $dir && docker build --progress=plain --platform linux/amd64 $*" 2>&1); rc=$?
  if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -q -e "$pat"; then echo "ok   $n"
  else echo "FAIL $n (exit $rc, wanted a failure matching: $pat)"; printf '%s\n' "$out" | tail -6; rc_all=1; fi
}
C="-f docker/cadex/Dockerfile"; O="-f docker/oda/Dockerfile"
expect_fail "cadex: no build args"       "set --build-arg CADEX_ARTIFACT"                    $C .
expect_fail "cadex: artifact missing"    "vendor/cadex/nope.bin is missing"                  $C --build-arg CADEX_ARTIFACT=nope.bin --build-arg CADEX_SHA256=$good --build-arg CADEX_VERSION=v .
expect_fail "cadex: wrong pinned hash"   "Refusing to use a different artifact"              $C --build-arg CADEX_ARTIFACT=dummy.bin --build-arg CADEX_SHA256=$bad --build-arg CADEX_VERSION=v .
expect_fail "cadex: reaches the install placeholder" "install.sh is a placeholder"           $C --build-arg CADEX_ARTIFACT=dummy.bin --build-arg CADEX_SHA256=$good --build-arg CADEX_VERSION=v .
expect_fail "oda: no build args"         "set --build-arg ODA_DRAWINGS_ARTIFACT"             $O .
expect_fail "oda: artifact missing"      "vendor/oda/nope.bin is missing"                    $O --build-arg ODA_DRAWINGS_ARTIFACT=nope.bin --build-arg ODA_DRAWINGS_SHA256=$good --build-arg ODA_STEP_ARTIFACT=dummy-b.bin --build-arg ODA_STEP_SHA256=$good .
expect_fail "oda: wrong pinned hash"     "Refusing to use a different SDK"                   $O --build-arg ODA_DRAWINGS_ARTIFACT=dummy-a.bin --build-arg ODA_DRAWINGS_SHA256=$bad --build-arg ODA_STEP_ARTIFACT=dummy-b.bin --build-arg ODA_STEP_SHA256=$good .
expect_fail "oda: reaches the install placeholder" "install.sh is a placeholder"               $O --build-arg ODA_DRAWINGS_ARTIFACT=dummy-a.bin --build-arg ODA_DRAWINGS_SHA256=$good --build-arg ODA_STEP_ARTIFACT=dummy-b.bin --build-arg ODA_STEP_SHA256=$good .
exit $rc_all
