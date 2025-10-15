from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import build123d as bd
from build123d_ease import show
from loguru import logger


@dataclass
class Spec:
    """Specification for thumb_key."""

    key_top_thickness: float = 1.5

    lip_width: float = 2.0
    lip_height: float = 1.0

    corner_z_fillet_radius: float = 2.0
    top_face_fillet_radius: float = 1.9

    orig_simplified_key_top_z: float = 3.65

    # Rotation on the right-hand key, compared to all other keys.
    key_rotation_angle_deg: float = -60

    # Chicago Steno style concave parameters
    # The dish is ellipsoidal with vertical ridges
    dish_depth: float = 0.9  # How deep the dish depression is
    dish_width_radius: float = 20.0  # X-axis radius (wider)
    dish_length_radius: float = (
        12.0  # Y-axis radius (narrower for vertical orientation)
    )
    dish_rotate_angle_deg: float = -60

    input_simplified_key_path: Path = (
        Path(__file__).parent / "simplified" / "simplified_key.step"
    )

    # Consider the key for the right hand.
    # View in normal top view.
    # Coordinates are relative to the key center.
    # Goes around clockwise.
    # Key center is (105, 127).
    new_key_outline_coords: tuple[tuple[float, float], ...] = (
        (5.5, 10.0),  # Concave point on top edge. (110.5, 117)
        (15.0, 10.0),  # Right edge, top.
        (15.0, -8.0),  # Right edge meets bottom edge.
        (-5.0, -8.0),  # Bottom edge, left.
        (-13.3, 6.3),  # Far left point.
        (0, 16.1),  # Top edge, left side.
        (5.5, 16.1),  # Far top point, straight above concave.
    )

    def __post_init__(self) -> None:
        """Post initialization checks."""
        assert self.input_simplified_key_path.is_file()

    def read_simplified_key_stem(self) -> bd.Compound:
        """Read the input key from the specified path.

        Centered on X-Y origin. Z is somewhat arbitrary but works out.
        Defined in `orig_simplified_key_top_z`.
        """
        p = bd.import_step(self.input_simplified_key_path)
        logger.debug(f"Imported key bounding box: {p.bounding_box()}")
        return p


def almost_equals(a: float, b: float, tol: float = 1e-3) -> bool:
    """Return whether two floats are almost equal."""
    return abs(a - b) < tol


def draw_new_key_outline(spec: Spec) -> bd.Polygon:
    """Draw the new key outline."""
    outline = bd.Polygon(
        *spec.new_key_outline_coords,
        align=None,  # Critical, otherwise it centers the shape.
    )

    return outline


def fillet_vertical_walls(
    part: bd.Part, radius: float | Literal["max"]
) -> bd.Part:
    """Apply fillet to vertical walls of the part."""
    max_fillet_radius = part.max_fillet(
        edge_list=part.edges().filter_by(bd.Axis.Z), max_iterations=100
    )
    logger.debug(f"Max fillet radius: {max_fillet_radius:.2f}")

    if radius == "max":
        radius = max_fillet_radius

    return part.fillet(
        radius=radius,
        edge_list=part.edges().filter_by(bd.Axis.Z),
    )


def create_chicago_steno_dish(spec: Spec, key_outline: bd.Polygon) -> bd.Part:
    """Create a Chicago Steno style dish with vertical ridges.

    Creates an ellipsoidal dish depression oriented vertically (longer in Y)
    with subtle vertical ridges that help guide finger placement.
    """
    # Get the center of the key outline
    bbox = key_outline.bounding_box()
    center_x = (bbox.min.X + bbox.max.X) / 2
    center_y = (bbox.min.Y + bbox.max.Y) / 2

    # Create the main ellipsoidal dish
    # Scale a sphere to create an ellipsoid
    dish_sphere = bd.Part(None) + bd.Sphere(radius=1.0)

    # Scale to create ellipsoid: wider in X, narrower in Y for vertical feel
    dish_ellipsoid = bd.scale(
        dish_sphere,
        (
            spec.dish_width_radius,
            spec.dish_length_radius,
            spec.dish_depth * 2,  # Z scaling for depth
        ),
    )

    # Position the ellipsoid to create the dish
    dish_center_z = (
        spec.key_top_thickness - spec.dish_depth + spec.dish_depth * 2
    )
    dish_ellipsoid = dish_ellipsoid.translate(
        (center_x, center_y, dish_center_z)
    ).rotate(bd.Axis.Z, angle=spec.dish_rotate_angle_deg)
    assert isinstance(dish_ellipsoid, bd.Part)
    return dish_ellipsoid


def make_thumb_key_rh(spec: Spec) -> bd.Part | bd.Compound:
    """Create a CAD model of thumb_key."""
    p = bd.Part(None)

    new_key_outline = draw_new_key_outline(spec)

    key_top = bd.extrude(
        new_key_outline,
        amount=spec.key_top_thickness,
        dir=(0, 0, 1),  # Force extruding up.
    )

    # Round the key_top edges.
    key_top = fillet_vertical_walls(
        key_top, radius=spec.corner_z_fillet_radius
    )

    # Create the lip.
    new_key_lip_outline = bd.offset(new_key_outline, amount=-spec.lip_width)
    assert isinstance(new_key_lip_outline, bd.Face | bd.Sketch)
    key_lip = fillet_vertical_walls(
        bd.extrude(
            new_key_outline,
            amount=spec.lip_height,
            dir=(0, 0, -1),  # Force extruding down.
        ),
        radius=spec.corner_z_fillet_radius,
    ) - fillet_vertical_walls(
        bd.extrude(
            new_key_lip_outline,
            amount=spec.lip_height,
            dir=(0, 0, -1),  # Force extruding down.
        ),
        radius="max",
    )

    key_top_and_lip = (
        bd.Part(None)
        # Add key_top, Z=0 is bottom of key_top.
        + key_top
        # Add key_lip, Z=0 is top of key_lip.
        + key_lip
    )

    # Round the top of the lip.
    key_top_and_lip = key_top_and_lip.fillet(
        radius=spec.top_face_fillet_radius,
        edge_list=(  # All edges on the top face.
            key_top_and_lip.faces().sort_by(bd.Axis.Z)[-1].edges()
        ),
    )

    p += key_top_and_lip

    # Add the key stem.
    p += (
        spec.read_simplified_key_stem()
        .rotate(axis=bd.Axis.Z, angle=spec.key_rotation_angle_deg)
        .translate(
            (
                0,
                0,
                # Move so that the top of the original key stem is at the top
                # of the new key top.
                -spec.orig_simplified_key_top_z + spec.key_top_thickness,
            )
        )
    )

    # Apply Chicago Steno style dish to the key top.
    chicago_dish = create_chicago_steno_dish(spec, new_key_outline)
    p -= chicago_dish

    return p


def make_mirror_thumb_key_lh(spec: Spec) -> bd.Part | bd.Compound:
    """Create a mirrored CAD model of thumb_key."""
    main_part = make_thumb_key_rh(spec)

    mirror_part = main_part.mirror(bd.Plane.YZ)

    return mirror_part


def preview(spec: Spec) -> bd.Part | bd.Compound:
    """Create a preview CAD model of thumb_key."""
    p = bd.Part(None)
    p += make_thumb_key_rh(spec).translate((15, 0, 0))
    p += make_mirror_thumb_key_lh(spec).translate((-15, 0, 0))

    return p


def boring_normal_key() -> bd.Compound:
    """Create a boring normal key for comparison."""
    p = bd.Part(None)

    p += bd.Box(
        17.3,
        16.1,
        4.75,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    return p


if __name__ == "__main__":
    logger.info("Starting renders.")
    parts = {
        "thumb_key_rh": show(make_thumb_key_rh(Spec())),
        "preview": show(preview(Spec())),
        "thumb_key_lh": (make_mirror_thumb_key_lh(Spec())),
        "boring_normal_key": boring_normal_key(),
    }

    logger.info("Showing CAD model(s)")

    (export_folder := Path(__file__).parent.with_name("build")).mkdir(
        exist_ok=True
    )
    for name, part in parts.items():
        assert isinstance(part, bd.Part | bd.Solid | bd.Compound), (
            f"{name} is not an expected type ({type(part)})"
        )
        if not part.is_manifold:
            logger.warning(f"Part '{name}' is not manifold")

        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info("Done exports.")
