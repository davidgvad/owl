"""Shared adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class AdapterResult:
    output_dir: Path
    warnings: List[str] = field(default_factory=list)


class DatasetAdapter:
    name = "dataset"

    def convert(self, input_dir: Path, output_dir: Path) -> AdapterResult:
        raise NotImplementedError
