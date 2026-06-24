"""WNTR/EPANET network adapter placeholder."""

from pathlib import Path

from .base import AdapterResult, DatasetAdapter


class WntrAdapter(DatasetAdapter):
    name = "WNTR"

    def convert(self, input_dir: Path, output_dir: Path) -> AdapterResult:
        raise NotImplementedError(
            "WNTR conversion should read EPANET INP/WNTR models and emit network.geojson "
            "plus pressure/flow metadata aligned to robot_state.csv."
        )
