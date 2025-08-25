from dataclasses import dataclass
from pathlib import Path

import build123d as bd
from build123d_ease import show
from loguru import logger

# TODO: Round/curve the top.


@dataclass
class Spec:
    """Specification for thumb_key."""

    lip_width: float = 2.0
    lip_height: float = 1.0

    corner_z_fillet: float = 3

    orig_simplified_key_top_z: float = 2.5 + 1.2
    orig_simplified_key_bottom_z: float = 1.0 + 1.2

    # Key bounding box and forced center, as absolute PCB coordinates.
    new_key_pcb_right_edge_x: float = 120.1
    new_key_pcb_bottom_edge_y: float = 143.5
    new_key_pcb_top_edge_y: float = 110.7
    new_key_pcb_left_edge_x: float = 90.4
    new_key_pcb_center_x: float = 105.0
    new_key_pcb_center_y: float = 127.0

    input_simplified_key_path: Path = (
        Path(__file__).parent / "simplified" / "simplified_key.step"
    )

    new_key_outline_coords: tuple[tuple[float, float], ...] = (
        (0, -6.6),
        # (0, 11.5),  # Commented to remove the tiny line.
        (-1.5, 11.5),  # Commented to remove the tiny line.
        (-16, 20),
        (-29.7, -3.7),
        (-14, -12.8),
        (-10.4, -6.5),
    )

    def __post_init__(self) -> None:
        """Post initialization checks."""
        assert self.input_simplified_key_path.is_file()

        assert (
            self.new_key_pcb_top_edge_y
            < self.new_key_pcb_center_y
            < self.new_key_pcb_bottom_edge_y
        )
        assert (
            self.new_key_pcb_left_edge_x
            < self.new_key_pcb_center_x
            < self.new_key_pcb_right_edge_x
        )

    def read_simplified_key(self) -> bd.Compound:
        """Read the input key from the specified path."""
        return bd.import_step(self.input_simplified_key_path)


def almost_equals(a: float, b: float, tol: float = 1e-3) -> bool:
    """Return whether two floats are almost equal."""
    return abs(a - b) < tol


def draw_new_key_outline(spec: Spec) -> bd.Polygon:
    """Draw the new key outline."""
    outline = bd.Polygon(*spec.new_key_outline_coords)

    # Validate bounding box vs. settings.
    assert almost_equals(
        outline.bounding_box().size.X,
        spec.new_key_pcb_right_edge_x - spec.new_key_pcb_left_edge_x,
    ), (
        f"Outline width {outline.bounding_box().size.X} != expected "
        f"{spec.new_key_pcb_right_edge_x - spec.new_key_pcb_left_edge_x}"
    )
    assert almost_equals(
        outline.bounding_box().size.Y,
        spec.new_key_pcb_bottom_edge_y - spec.new_key_pcb_top_edge_y,
    ), (
        f"Outline height {outline.bounding_box().size.Y} != expected "
        f"{spec.new_key_pcb_bottom_edge_y - spec.new_key_pcb_top_edge_y}"
    )

    # Shift outline to the correct position.
    outline = outline.translate(
        (
            -outline.bounding_box().min.X
            + (spec.new_key_pcb_left_edge_x - spec.new_key_pcb_center_x),
            -outline.bounding_box().min.Y
            + (spec.new_key_pcb_top_edge_y - spec.new_key_pcb_center_y),
        ),
    )

    return outline


def fillet_vertical_walls(part: bd.Part, radius: float) -> bd.Part:
    """Apply fillet to vertical walls of the part."""
    return part.fillet(
        radius=radius,
        edge_list=part.edges().filter_by(bd.Axis.Z),
    )
    return part


def make_thumb_key(spec: Spec) -> bd.Part | bd.Compound:
    """Create a CAD model of thumb_key."""
    p = bd.Part(None)

    p += spec.read_simplified_key()

    new_key_outline = draw_new_key_outline(spec)

    key_top = bd.extrude(
        new_key_outline,
        amount=abs(
            spec.orig_simplified_key_bottom_z - spec.orig_simplified_key_top_z
        ),
    ).translate(
        (0, 0, spec.orig_simplified_key_bottom_z),
    )

    # Round the key_top edges.
    key_top = fillet_vertical_walls(key_top, radius=spec.corner_z_fillet)

    # Create the lip.
    new_key_lip_outline = bd.offset(new_key_outline, amount=-spec.lip_width)
    assert isinstance(new_key_lip_outline, bd.Face | bd.Sketch)
    key_lip = (
        fillet_vertical_walls(
            bd.extrude(new_key_outline, amount=spec.lip_height),
            radius=spec.corner_z_fillet,
        )
        - fillet_vertical_walls(
            bd.extrude(new_key_lip_outline, amount=spec.lip_height),
            radius=spec.corner_z_fillet,
        )
    ).translate(
        (0, 0, spec.orig_simplified_key_bottom_z - spec.lip_height),
    )

    key_top_and_lip = bd.Part(None) + key_lip + key_top

    p += key_top_and_lip

    return p


if __name__ == "__main__":
    logger.info("Starting.")
    parts = {
        "thumb_key": show(make_thumb_key(Spec())),
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
