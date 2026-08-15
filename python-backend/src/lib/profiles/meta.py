"""Read and write profile metadata files."""

import json
from pathlib import Path
from typing import cast

from src.config import config_dirs


class Meta:
    @staticmethod
    def active_meta_path(profile_name: str | None = None) -> Path:
        profile = profile_name or "default"
        return config_dirs.PROFILES_DIR / f"{profile}.meta.json"

    def read_active_meta(self, profile_name: str | None = None) -> dict[str, object]:
        try:
            with self.active_meta_path(profile_name).open(encoding="utf-8") as meta_file:
                return cast(dict[str, object], json.load(meta_file))
        except (OSError, ValueError, TypeError):
            return {}

    def write_active_meta(self, meta: dict[str, object], profile_name: str | None = None) -> None:
        with self.active_meta_path(profile_name).open("w", encoding="utf-8") as meta_file:
            json.dump(meta, meta_file)

    def meta_path(self, name: str) -> Path:
        return config_dirs.PROFILES_DIR / f"{name}.meta.json"
