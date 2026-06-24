"""GPLA-12 acoustic leakage adapter placeholder."""

from pathlib import Path

from .base import AdapterResult, DatasetAdapter


class Gpla12Adapter(DatasetAdapter):
    name = "GPLA-12"

    def convert(self, input_dir: Path, output_dir: Path) -> AdapterResult:
        raise NotImplementedError(
            "GPLA-12 conversion should emit hydrophone.wav plus acoustic_features.csv "
            "with source labels mapped to leak/no-leak training targets."
        )
