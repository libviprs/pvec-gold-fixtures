#!/bin/sh
# Unpacks the two SDKs and builds docker/oda/src/oda_dwg2step.cpp against them.
#
# NOT WRITTEN YET. It needs the SDK headers, libraries and licence-activation call, which are not
# available here, and the wrapper itself is written against the SDK API. See
# docs/converters/oda-qualification.md for the contract the wrapper has to meet (the CLI, the
# exit-code table, the JSON error record).
echo "oda-converter: docker/oda/install.sh is a placeholder until the SDK artifacts are available" >&2
exit 1
