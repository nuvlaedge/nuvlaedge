from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class NuvlaID(str):
    @property
    def resource(self) -> str:
        parts = self.split("/")
        return parts[0] if len(parts) > 1 else ''

    @property
    def uuid(self) -> str:
        return self.rsplit("/", 1)[-1]

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, handler(str))

    def validate(self) -> bool:
        values: list = self.split("/")
        if len(values) != 2:
            return False
        return True
