#!/bin/sh
# Installs the vendor artifact into /opt/cadex and writes the two glue commands that
# tools/convert_cadex.sh calls:
#   /opt/cadex/bin/convert-cmd <in.dwg> <out.step>   exit 0, or one of 11..16 (see convert_cadex.sh)
#   /opt/cadex/bin/product-version                   one line, the product build
#
# NOT WRITTEN YET. It depends on the layout and command line of the CAD Exchanger Batch build the
# licensee supplies, which is not available here, and guessing them would only look finished.
# See docs/converters/cadex-qualification.md for what this step has to produce.
echo "cadex-converter: docker/cadex/install.sh is a placeholder until the vendor artifact is available" >&2
exit 1
