"""
Address Routes
───────────────
Handles HTTP layer only for address endpoints.
No business logic here — all rules live in AddressService.

Endpoints:
    GET    /addresses              → search + list (all filters + pagination)
    POST   /addresses              → create a new address
    GET    /addresses/{id}         → get a single address
    PATCH  /addresses/{id}         → partially update an address
    DELETE /addresses/{id}         → delete an address
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_address_service
from app.models.address import Address
from app.schemas.address import (
    AddressCreate,
    AddressFilterParams,
    AddressOut,
    AddressUpdate,
    PaginatedResponse,
)
from app.services.address_service import AddressService

logger = logging.getLogger(__name__)

# prefix and tags apply to all routes in this file
router = APIRouter(
    prefix="/addresses",
    tags=["Addresses"],
)


@router.get(
    "/",
    response_model=PaginatedResponse[AddressOut],
    summary="Search and list addresses",
    description=(
        "Search addresses near your location.\n\n"
        "**latitude and longitude are required** — provide your coordinates.\n\n"
        "**distance defaults to 5km** if not provided.\n\n"
        "Examples:\n"
        "- `?latitude=52.37&longitude=4.89` → everything within 5km\n"
        "- `?latitude=52.37&longitude=4.89&distance=10` → within 10km\n"
        "- `?entity_type=restaurant&latitude=52.37&longitude=4.89` → restaurants within 5km\n"
        "- `?name=john&entity_type=home&latitude=52.37&longitude=4.89&distance=20` → combined"
    ),
)
async def list_addresses(
    # coordinates — required
    latitude: float = Query(
        ...,
        ge=-90,
        le=90,
        description="Your current location latitude. Required.",
    ),
    longitude: float = Query(
        ...,
        ge=-180,
        le=180,
        description="Your current location longitude. Required.",
    ),
    distance: float = Query(
        5.0,
        gt=0,
        description="Search distance in km. Defaults to 5km.",
    ),
    # search filters — optional
    name: Optional[str] = Query(
        None,
        description="Partial name match. 'Udupi ' matches 'Udupi grand Hotel', 'Udupi Hotel'",
    ),
    entity_type: Optional[str] = Query(
        None,
        description="Fuzzy type match. 'resto' matches 'restaurant'",
    ),
    # distance — optional, defaults to 5km
    
    # pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Results per page"),
    service: AddressService = Depends(get_address_service),
) -> PaginatedResponse[AddressOut]:
    logger.info(
        f"Route: GET /addresses "
        f"lat={latitude} lon={longitude} distance={distance} "
        f"name={name} entity_type={entity_type} "
        f"page={page} page_size={page_size}"
    )
    params = AddressFilterParams(
        latitude=latitude,
        longitude=longitude,
        distance=distance,
        name=name,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )
    return await service.search_addresses(params)


@router.post(
    "/",
    response_model=AddressOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address",
    description=(
        "Create a new address with coordinates. "
        "entity_type_id must reference an existing entity type. "
        "Latitude must be between -90 and 90. "
        "Longitude must be between -180 and 180."
    ),
)
async def create_address(
    data: AddressCreate,
    service: AddressService = Depends(get_address_service),
) -> Address:
    """
    Create a new address.
    Returns 404 if entity_type_id does not exist.
    """
    logger.info(
        f"Route: POST /addresses "
        f"entity_name={data.entity_name} city={data.city}"
    )
    return await service.create_address(data)


@router.get(
    "/{address_id}",
    response_model=AddressOut,
    summary="Get a single address",
    description="Retrieve a single address by its ID.",
)
async def get_address(
    address_id: int,
    service: AddressService = Depends(get_address_service),
) -> Address:
    """
    Fetch a single address by ID.
    Returns 404 if not found.
    """
    logger.info(f"Route: GET /addresses/{address_id}")
    return await service.get_address_by_id(address_id)


@router.patch(
    "/{address_id}",
    response_model=AddressOut,
    summary="Partially update an address",
    description=(
        "Update only the fields you provide. "
        "Fields not included in the request body are left unchanged. "
        "This is a PATCH — not a full replacement (PUT)."
    ),
)
async def update_address(
    address_id: int,
    data: AddressUpdate,
    service: AddressService = Depends(get_address_service),
) -> Address:
    """
    Partially update an address.
    Returns 404 if address not found.
    Returns 404 if new entity_type_id does not exist.
    """
    logger.info(f"Route: PATCH /addresses/{address_id}")
    return await service.update_address(address_id, data)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an address",
    description="Permanently delete an address by its ID.",
)
async def delete_address(
    address_id: int,
    service: AddressService = Depends(get_address_service),
) -> None:
    """
    Delete an address.
    Returns 404 if not found.
    """
    logger.info(f"Route: DELETE /addresses/{address_id}")
    await service.delete_address(address_id)