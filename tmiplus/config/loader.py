from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from tmiplus.config.schema import RootConfig

CONFIG_PATH = Path.home() / ".tmi.yml"


def ensure_config() -> RootConfig:
    if not CONFIG_PATH.exists():
        cfg = RootConfig()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg.model_dump(), f, sort_keys=False, allow_unicode=True)
        return cfg
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return cast(RootConfig, RootConfig.model_validate(data))


def save_config(cfg: RootConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg.model_dump(), f, sort_keys=False, allow_unicode=True)
