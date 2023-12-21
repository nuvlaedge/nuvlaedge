import logging
from dataclasses import dataclass


logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class TrackedResource:
    resource: str
    fields: set[str]

    last_update_time: float
    update_period: float = 60


@dataclass
class ResourceTracker:
    resources: dict[str, TrackedResource]

    def add_field(self, resource: str, field: str):
        if resource not in self.resources:
            logger.debug(f"Adding resource {resource} to the tracker")
            self.resources[resource] = TrackedResource(resource, set(), 0, 0)
        self.resources[resource].fields.add(field)
        logger.debug(f"Added field {field} to resource {resource}")

    def remove_field(self, resource: str, field: str):
        if resource not in self.resources or field not in self.resources[resource].fields:
            logger.debug(f"Trying to remove field {field} from resource {resource} but it does not exist")
            return

        self.resources[resource].fields.remove(field)
        logger.debug(f"Removed field {field} from resource {resource}")

    def get_fields(self, resource: str) -> set[str]:
        if resource not in self.resources:
            return set()
        return self.resources[resource].fields

    def resource_summary(self) -> None:
        logger.info(f"Resource tracker summary: ")

        for resource, tracked_resource in self.resources.items():
            logger.info(f"Resource: {resource} \n "
                        f"Fields: {tracked_resource.fields} \n"
                        f"Last update time: {tracked_resource.last_update_time} \n"
                        f"Update period: {tracked_resource.update_period}")
