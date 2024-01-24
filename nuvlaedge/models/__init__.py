import json
import logging

from pydantic import BaseModel

from nuvlaedge.common.nuvlaedge_logging import get_nuvlaedge_logger

logger: logging.Logger = get_nuvlaedge_logger(__name__)


def are_models_equal(model_one: BaseModel, model_two: BaseModel):
    """
    Compares two BaseModel objects and returns True if they are equal, False otherwise.

    Args:
        model_one (BaseModel): The first BaseModel object to be compared.
        model_two (BaseModel): The second BaseModel object to be compared.

    Returns:
        bool: True if the BaseModel objects are equal, False otherwise.

    """
    return (model_one.model_dump(exclude_none=True, by_alias=False) ==
            model_two.model_dump(exclude_none=True, by_alias=False))


def model_diff(reference: BaseModel, target: BaseModel) -> tuple[set[str], set[str]]:
    """
    Calculate the differences between two models.

    Args:
        reference (BaseModel): The reference model to compare against.
        target (BaseModel): The target model to compare with.

    Returns:
        tuple[set[str], set[str]]: A tuple containing two sets. The first set contains the fields that have different
         values between the reference and target models. The second set contains the fields that exist in the
         reference model but not in the target model.
    """
    to_send: set = set()
    to_delete: set = set()

    for field, value in iter(target):
        if value != getattr(reference, field):
            if value is not None:
                to_send.add(field)
            else:
                to_delete.add(field.replace('_', '-'))

    return to_send, to_delete
