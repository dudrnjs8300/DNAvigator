"""Pure-Python (Qt-free) zoom/pan/rotation state for the circular genome map.

Mirrors the linear canvas's ViewportTransform pattern: all the math lives
here, unit-testable without a real GUI event loop; CircularGenomeCanvas only
does the Qt painting/event plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

MIN_ZOOM_SCALE = 1.0
MAX_ZOOM_SCALE = 8.0


@dataclass(frozen=True, slots=True)
class CircularViewportTransform:
    zoom_scale: float = 1.0
    rotation_degrees: float = 0.0
    pan_x: float = 0.0
    pan_y: float = 0.0

    def zoomed(
        self, factor: float, anchor_offset_x: float = 0.0, anchor_offset_y: float = 0.0
    ) -> CircularViewportTransform:
        """Zoom by ``factor``, keeping whatever was under the zoom anchor
        (e.g. the mouse cursor) in the same screen position instead of
        always ballooning outward from the ring's center. ``anchor_offset_x/y``
        is the anchor's screen position minus the *current* ring center
        (caller's job, since only the caller -- the canvas -- knows widget
        geometry); pass ``0, 0`` to zoom on the center, as before.

        Without this, repeatedly zooming in on a gene away from dead center
        just grows the ring radius around a fixed center, drifting that gene
        off toward the edge (or entirely out) of the viewport instead of
        magnifying where the user is actually looking -- a circular ring's
        own center is empty background, not more ring.
        """
        new_scale = min(MAX_ZOOM_SCALE, max(MIN_ZOOM_SCALE, self.zoom_scale * factor))
        # The *actual* scale ratio applied, which can differ from the
        # requested `factor` once clamped at MIN/MAX_ZOOM_SCALE -- using the
        # unclamped factor here would introduce a pan drift bug right at the
        # zoom limits.
        actual_factor = new_scale / self.zoom_scale if self.zoom_scale else 1.0
        pan_dx = (1 - actual_factor) * anchor_offset_x
        pan_dy = (1 - actual_factor) * anchor_offset_y
        transform = replace(
            self, zoom_scale=new_scale, pan_x=self.pan_x + pan_dx, pan_y=self.pan_y + pan_dy
        )
        # zooming back out to the minimum re-centers the view -- otherwise a
        # pan applied while zoomed in would leave the ring stuck off-center
        # once it no longer fills the viewport.
        if new_scale <= MIN_ZOOM_SCALE:
            transform = replace(transform, pan_x=0.0, pan_y=0.0)
        return transform

    def rotated(self, delta_degrees: float) -> CircularViewportTransform:
        return replace(self, rotation_degrees=(self.rotation_degrees + delta_degrees) % 360.0)

    def panned(self, dx: float, dy: float) -> CircularViewportTransform:
        return replace(self, pan_x=self.pan_x + dx, pan_y=self.pan_y + dy)

    def reset(self) -> CircularViewportTransform:
        return CircularViewportTransform()

    @property
    def is_at_default(self) -> bool:
        return (
            self.zoom_scale == 1.0
            and self.rotation_degrees == 0.0
            and self.pan_x == 0.0
            and self.pan_y == 0.0
        )
