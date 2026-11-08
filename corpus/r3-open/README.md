# r3-open (candidate)

Adds the viewport, paper-space and large-industrial fixtures libviprs#1055 and #1064 need (#96) on top of `r2-open`, which it includes unchanged.

## Record shape

A fixture with viewports carries a `viewports` array in `expected.math.json`: per viewport `id`, `layout`, `paper` (`center`, `width`, `height`, in paper space), `view` (`center`, `height`, the model-space window; the target is the origin, so the centre is the model point at the middle of the viewport) and, when it is clipped, `clip` (`polygon` in paper space, `bounded_only`, `bounds`). `bounded_only` means a reader may report the polygon or only its bounding box, and may not report anything outside `bounds`. A paper-space layout is the set of viewports that share a `layout` name. Assertions use `VIEWPORT_COUNT_PRESERVED` and `VIEWPORT_CLIP_PRESERVED`.

The print-profile probes (#101) add a `layers` table with plot flags, lines on named layers in model and paper space (`space: PAPER`), and per viewport a view `direction` and `twist` (radians), `frozen_layers`, `hide_plot` and `entity_layer`, plus the layout's plot settings in `layout_plot`. Their claims are `VIEWPORT_VIEW_PRESERVED`, `VIEWPORT_FREEZE_PRESERVED`, `VIEWPORT_PLOT_STATE_PRESERVED`, `LAYER_PLOT_STATE_PRESERVED` and `LAYOUT_PLOT_SETTINGS_PRESERVED`.

The large fixture has no DWG, only a generator and a size class (`size_class: large`).
