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

router = APIRouter(
    prefix="/entity-types",
    tags=["Entity Types"],
)




@router.get(
    "/",
    response_model=list[EntityTypeOut],
    summary="List all entity types",
    description=(
        "Returns all available entity types — both system defaults and "
        "any custom ones you have created.\n\n"

        "---\n\n"

        "### Default entity types\n"
        "These are seeded automatically when the app starts "
        "and **cannot be deleted**:\n\n"
        "| ID | Name | is_default |\n"
        "|----|------|------------|\n"
        "| 1 | home | true |\n"
        "| 2 | work | true |\n"
        "| 3 | business | true |\n"
        "| 4 | other | true |\n\n"

        "---\n\n"

        "### Custom entity types\n"
        "Any types you create via `POST /entity-types` will appear here "
        "with `is_default: false`. "
        "These can be deleted using `DELETE /entity-types/{id}`.\n\n"

        "Use the `id` from this list when creating an address — "
        "pass it as `entity_type_id` in `POST /addresses`."
    ),
)
async def list_entity_types(
    service: AddressService = Depends(get_address_service),
) -> list[EntityType]:
    """
    Fetch all entity types.
    is_default=True  → seeded at startup, cannot be deleted.
    is_default=False → created by user via API, can be deleted.
    """
    logger.info("Route: GET /entity-types")
    return await service.get_all_entity_types()





@router.post(
    "/",
    response_model=EntityTypeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom entity type",
    description=(
        "Create a new custom entity type to categorise your addresses.\n\n"

        "---\n\n"

        "### How it works\n"
        "- Provide a `name` for the new type (e.g. `restaurant`, `gym`, `hotel`).\n"
        "- Names are stored **lowercase** automatically — `Restaurant` becomes `restaurant`.\n"
        "- Names must be **unique** — creating a duplicate returns `409 Conflict`.\n"
        "- The new type will have `is_default: false` — meaning it can be deleted later.\n\n"

        "---\n\n"

        "### Using the new type\n"
        "Once created, copy the `id` from the response and use it as "
        "`entity_type_id` when creating an address in `POST /addresses`.\n\n"

        "---\n\n"

        "### Default types (already available)\n"
        "You don't need to create these — they exist by default:\n"
        "`home`, `work`, `business`, `other`\n\n"

        "---\n\n"

        "### Error responses\n"
        "- `409 Conflict` — an entity type with this name already exists."
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
    summary="Delete a custom entity type",
    description=(
        "Delete a user-created entity type by its ID.\n\n"

        "---\n\n"

        "### Rules\n"
        "- **Default types cannot be deleted** — `home`, `work`, `business`, `other` "
        "are protected. Attempting to delete them returns `403 Forbidden`.\n"
        "- Only custom types (`is_default: false`) created via "
        "`POST /entity-types` can be deleted.\n\n"

        "---\n\n"

        "### Error responses\n"
        "- `404 Not Found` — entity type with this ID does not exist.\n"
        "- `403 Forbidden` — attempting to delete a protected default type."
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