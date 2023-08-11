import logging
import tomllib
from typing import Callable

from pydantic import BaseSettings

from pathlib import Path

logger: logging.Logger = logging.getLogger('settings')
SettingsSourceCallable = Callable[[str], any]


class NuvlaConfig(BaseSettings):
    @classmethod
    def from_toml(cls, config_file: Path):
        if not config_file.exists() or not config_file.is_file():
            raise FileNotFoundError(f'File {config_file}')

        with config_file.open('r') as f:
            config_dict = tomllib.loads(f.read())
            return cls.parse_obj(config_dict)

    class Config:
        @classmethod
        def customise_sources(
                cls,
                init_settings: SettingsSourceCallable,
                env_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            """
            Allow overwriting file defined settings with environmental variables
            """
            return env_settings, init_settings
