"""

"""
from pydantic import BaseModel


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

    class Config:
        """ Configuration class for base telemetry data """
        exclude_none = True
        allow_population_by_field_name = True
        alias_generator = underscore_to_hyphen
        validate_assignment = True
