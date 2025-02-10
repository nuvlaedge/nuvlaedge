from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from threading import Lock


def underscore_to_hyphen(field_name: str) -> str:
    """
    Alias generator that takes the field name and converts the underscore into hyphen
    Args:
        field_name: string that contains the name of the field to be processed

    Returns: the alias name with no underscores

    """
    return field_name.replace("_", "-")


class NuvlaEdgeBaseModel(BaseModel):
    """
    Base data structure for providing a common configuration for all data structures.
    """
    """ Configuration class for base telemetry data """
    model_config = ConfigDict(populate_by_name=True,
                              use_enum_values=True,
                              arbitrary_types_allowed=True,
                              validate_assignment=True,
                              alias_generator=underscore_to_hyphen)


class NuvlaEdgeStaticModel(NuvlaEdgeBaseModel):
    update_lock: ClassVar[Lock] = Lock()

    def update(self, data: dict[str, any] | BaseModel):
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_none=True, by_alias=False)
        for k, v in data.items():
            parsed_key = k.replace('-', '_')
            if hasattr(self, parsed_key):
                with self.update_lock:
                    if isinstance(v, dict) and getattr(self, parsed_key) is not None:
                        getattr(self, parsed_key).update(v)
                    else:
                        self.__setattr__(parsed_key, v)
