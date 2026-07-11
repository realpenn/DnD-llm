from __future__ import annotations

from importlib.metadata import PackageNotFoundError, files
from pathlib import Path

_DISTRIBUTION_NAME = "dnd-llm"
_ATTRIBUTION_SUFFIX = "dnd_llm/rules_data/attribution.json"


def bundled_rules_data_dir() -> Path:
    source_tree = Path(__file__).resolve().parents[2] / "rules_data"
    if (source_tree / "attribution.json").is_file():
        return source_tree

    try:
        distribution_files = files(_DISTRIBUTION_NAME)
    except PackageNotFoundError as exc:
        raise FileNotFoundError("bundled rules_data could not be located") from exc

    if distribution_files is not None:
        for entry in distribution_files:
            normalized = str(entry).replace("\\", "/")
            if normalized.endswith(_ATTRIBUTION_SUFFIX):
                return Path(entry.locate()).resolve().parent

    raise FileNotFoundError("installed distribution does not contain rules_data")
