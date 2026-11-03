# r3-open (candidate)

Adds the viewport, paper-space and large-industrial fixtures libviprs#1055 and #1064 need (#96) on top of `r2-open`, which it includes unchanged.

## Record shape

A fixture with viewports carries a `viewports` array in `expected.math.json`: per viewport `id`, `layout`, `paper` (`center`, `width`, `height`, in paper space), `view` (`center`, `height`, the model-space window) and, when it is clipped, `clip` (`polygon` in paper space, `bounded_only`, `bounds`). `bounded_only` means a reader may report the polygon or only its bounding box, and may not report anything outside `bounds`. A paper-space layout is the set of viewports that share a `layout` name. Assertions use `VIEWPORT_COUNT_PRESERVED` and `VIEWPORT_CLIP_PRESERVED`.

The large fixture has no DWG, only a generator and a size class (`size_class: large`).
