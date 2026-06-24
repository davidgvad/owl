"""OceanShip background-noise adapter placeholder."""

from pathlib import Path

from .base import AdapterResult, DatasetAdapter


class OceanShipAdapter(DatasetAdapter):
    name = "OceanShip"

    def convert(self, input_dir: Path, output_dir: Path) -> AdapterResult:
        raise NotImplementedError(
            "OceanShip conversion should emit hydrophone.wav background-noise clips "
            "and metadata that marks them as non-leak hydrophone proxy data."
        )
