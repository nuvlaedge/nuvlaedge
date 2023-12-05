import logging
import toml
from typing import Callable

from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

logger: logging.Logger = logging.getLogger('settings')
SettingsSourceCallable = Callable[[str], any]


class NuvlaEdgeBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(arbitrary_types_allowed=True,
                                      populate_by_name=True)

    @classmethod
    def from_toml(cls, config_file: str | Path):
        if isinstance(config_file, str):
            config_file = Path(config_file)

        if not config_file.exists() or not config_file.is_file():
            raise FileNotFoundError(f'File {config_file}')

        with config_file.open('r') as f:
            config_dict = toml.loads(f.read())
            return cls.model_validate(config_dict)

    @classmethod
    def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable
    ) -> tuple[SettingsSourceCallable, ...]:
        """
        Allow overwriting file defined settings with environmental variables
        """
        return env_settings, init_settings, file_secret_settings  # pragma: no cover
