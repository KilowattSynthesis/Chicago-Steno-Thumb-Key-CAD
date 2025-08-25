from dataclasses import dataclass
from pathlib import Path

import build123d as bd
from loguru import logger


@dataclass
class Spec:
    """Specification for thumb_key."""

    thumb_key_radius: float = 20

    # shapes[0] has bounding box bbox:
    # -8.649541854858398 <= x <= 8.649541854858398
    # -8.049552917480469 <= y <= 8.049552917480469
    # -1.099999189376831 <= z <= 3.6499996185302734
    orig_key_size_x: float = 8.65 * 2
    orig_key_size_y: float = 8.05 * 2

    input_key_path: Path = (
        Path(__file__).parent
        / "input"
        / "kb_keycaps_chicago_stenographer__stl__single_keys__cs_r3x_1.stl"
    )

    def __post_init__(self) -> None:
        """Post initialization checks."""
        assert self.thumb_key_radius > 0, "thumb_key_radius must be positive"

    def read_input_key(self) -> list[bd.Shape]:
        """Read the input key from the specified path."""
        # return bd.import_step(self.input_key_path)
        m = bd.Mesher()
        shapes: list[bd.Shape] = m.read(self.input_key_path)

        logger.debug(
            f"Read {len(shapes)} shapes from {self.input_key_path.name}"
        )

        for i, shape in enumerate(shapes):
            logger.debug(
                f"shapes[{i}] has bounding box {shape.bounding_box()}"
            )

        return shapes


def simplified_key(spec: Spec) -> bd.Part | bd.Compound:
    """Create a CAD model of thumb_key."""
    p = bd.Part(None)

    p += spec.read_input_key()

    # Chop to only the important part.
    p &= bd.Box(8, 6, 100)

    return p


if __name__ == "__main__":
    logger.info("Starting.")
    parts = {
        "simplified_key": simplified_key(Spec()),
    }

    logger.info("Showing CAD model(s)")

    # Note: Special output folder here!
    (export_folder := (Path(__file__).parent / "simplified")).mkdir(
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
