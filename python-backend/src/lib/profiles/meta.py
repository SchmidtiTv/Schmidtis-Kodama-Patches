"""Read and write profile metadata files."""

import json
from pathlib import Path
from typing import Optional, cast

from src.config import config_dirs
from src.lib.security.file_names import require_safe_file_stem


class Meta:
    @staticmethod
    def active_meta_path(profile_name: Optional[str] = None) -> Path:
        profile = profile_name or "default"
        return config_dirs.PROFILES_DIR / f"{require_safe_file_stem(profile)}.meta.json"

    def read_active_meta(self, profile_name: Optional[str] = None) -> dict[str, object]:
        try:
            with self.active_meta_path(profile_name).open(encoding="utf-8") as meta_file:
                return cast(dict[str, object], json.load(meta_file))
        except (OSError, ValueError, TypeError):
            return {}

    def write_active_meta(self, meta: dict[str, object], profile_name: Optional[str] = None) -> None:
        with self.active_meta_path(profile_name).open("w", encoding="utf-8") as meta_file:
            json.dump(meta, meta_file)

    def meta_path(self, name: str) -> Path:
        return config_dirs.PROFILES_DIR / f"{require_safe_file_stem(name)}.meta.json"
