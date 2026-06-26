"""
Entity Type Routes
───────────────────
Handles HTTP layer only for entity type endpoints.
No business logic here — all rules live in AddressService.

Endpoints:
    GET    /entity-types          → list all entity types
    POST   /entity-types          → create a new entity type
    DELETE /entity-types/{id}     → delete a user-defined entity type
"""

import logging

from fastapi import APIRouter, Depends, status

from app.api.deps import get_address_service
from app.models.address import EntityType
from app.schemas.address import EntityTypeCreate, EntityTypeOut
from app.services.address_service import AddressService

logger = logging.getLogger(__name__)

# prefix and tags apply to all routes in this file
# prefix   → all routes start with /entity-types
# tags     → groups routes under "Entity Types" in Swagger docs
router = APIRouter(
    prefix="/entity-types",
    tags=["Entity Types"],
)


@router.get(
    "/",
    response_model=list[EntityTypeOut],
    summary="List all entity types",
    description=(
        "Returns all entity types including system defaults "
        "(home, work, business, other) and user-created ones."
    ),
)
async def list_entity_types(
    service: AddressService = Depends(get_address_service),
) -> list[EntityType]:
    """
    Fetch all entity types.
    is_default=True  → seeded via migration, cannot be deleted.
    is_default=False → created by user via API, can be deleted.
    """
    logger.info("Route: GET /entity-types")
    return await service.get_all_entity_types()


@router.post(
    "/",
    response_model=EntityTypeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new entity type",
    description=(
        "Create a custom entity type. "
        "Name must be unique (case insensitive). "
        "Names are stored lowercase automatically."
    ),
)
async def create_entity_type(
    data: EntityTypeCreate,
    service: AddressService = Depends(get_address_service),
) -> EntityType:
    """
    Create a new user-defined entity type.
    Returns 409 if the name already exists.
    """
    logger.info(f"Route: POST /entity-types name={data.name}")
    return await service.create_entity_type(data)


@router.delete(
    "/{entity_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an entity type",
    description=(
        "Delete a user-created entity type. "
        "Default types (home, work, business, other) "
        "are protected and cannot be deleted."
    ),
)
async def delete_entity_type(
    entity_type_id: int,
    service: AddressService = Depends(get_address_service),
) -> None:
    """
    Delete a user-defined entity type.
    Returns 404 if not found.
    Returns 403 if attempting to delete a default type.
    """
    logger.info(f"Route: DELETE /entity-types/{entity_type_id}")
    await service.delete_entity_type(entity_type_id)