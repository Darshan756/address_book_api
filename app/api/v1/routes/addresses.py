"""
Address Routes
───────────────
Handles HTTP layer only for address endpoints.
No business logic here — all rules live in AddressService.

Endpoints:
    GET    /addresses               → list all addresses
    GET    /addresses/search        → search with filters + pagination
    GET    /addresses/{id}          → get a single address
    POST   /addresses               → create a new address
    PATCH  /addresses/{id}          → partially update an address
    DELETE /addresses/{id}          → delete an address
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
    NearbySearchParams,
    PaginatedResponse,
)
from app.services.address_service import AddressService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/addresses",
    tags=["Addresses"],
)


@router.get(
    "/",
    response_model=list[AddressOut],
    summary="List all addresses",
    description="Returns all addresses with their full entity type details.",
)
async def list_addresses(
    service: AddressService = Depends(get_address_service),
) -> list[Address]:
    """Fetch all addresses."""
    logger.info("Route: GET /addresses")
    return await service.get_all_addresses()





@router.get(
    "/search",
    response_model=PaginatedResponse[AddressOut],
    summary="Search addresses near your location",
    description=(
        "Search addresses near your location with optional filters and pagination.\n\n"

        "---\n\n"

        "### Required parameters\n"
        "| Parameter | Description |\n"
        "|-----------|-------------|\n"
        "| `latitude` | Your current location latitude (-90 to 90) |\n"
        "| `longitude` | Your current location longitude (-180 to 180) |\n\n"

        "---\n\n"

        "### Optional filters\n\n"

        "**`entity_name`** — Filter by name using a **partial, case insensitive** match.\n"
        "You don't need the full name — any part of it works.\n"
        "- `john` → matches `John Doe`, `John Smith`, `Johnson Corp`\n"
        "- `cafe` → matches `Cafe Roma`, `Blue Cafe`, `Cafe on Main`\n"
        "- Leave empty to return all names.\n\n"

        "**`entity_type`** — Filter by entity type using **fuzzy matching**.\n"
        "You don't need to type the exact name — partial and misspelled terms work too.\n"
        "Matching is tried in this order:\n"
        "1. Exact match — `restaurant` → `restaurant`\n"
        "2. Partial match — `rest` → `restaurant`\n"
        "3. Fuzzy/typo match — `restrunt` → `restaurant`\n\n"
        "Default entity types you can use:\n"
        "- `home`, `work`, `business`, `other`\n"
        "- Any custom types you added via the **Entity Types** section below.\n"
        "- Leave empty to return all entity types.\n\n"

        "**`radius`** — Search radius in km (or miles if configured).\n"
        "- **Defaults to 5.0 if not provided** — no need to always specify it.\n"
        "- Example: `radius=10` → search within 10km of your location.\n\n"

        "---\n\n"

        "### Pagination\n"
        "- `page` — page number, starts at 1 (default: `1`)\n"
        "- `page_size` — results per page, max 100 (default: `10`)\n\n"

        "---\n\n"

        "### Examples\n"
        "```\n"
        "# everything within default 5km\n"
        "?latitude=52.37&longitude=4.89\n\n"
        "# everything within 10km\n"
        "?latitude=52.37&longitude=4.89&radius=10\n\n"
        "# restaurants within default 5km (fuzzy — 'resto' also works)\n"
        "?latitude=52.37&longitude=4.89&entity_type=restaurant\n\n"
        "# Johns within 20km\n"
        "?latitude=52.37&longitude=4.89&entity_name=john&radius=20\n\n"
        "# McDonalds-like restaurants within 10km, page 2\n"
        "?latitude=52.37&longitude=4.89&entity_name=mc&entity_type=restaurant&radius=10&page=2\n"
        "```"
    ),
)
async def search_addresses(
    # ── coordinates (required) ────────────────────────────────────────────────
    latitude: float = Query(
        ...,
        ge=-90,
        le=90,
        description=(
            "Your current location latitude (-90 to 90). "
            "Required — used to calculate distance to each address."
        ),
    ),
    longitude: float = Query(
        ...,
        ge=-180,
        le=180,
        description=(
            "Your current location longitude (-180 to 180). "
            "Required — used to calculate distance to each address."
        ),
    ),
    # ── search filters (all optional) ────────────────────────────────────────
    entity_name: Optional[str] = Query(
        None,
        description=(
            "Filter by entity name — partial, case insensitive match. "
            "You don't need the full name, any part works. "
            "'john' matches 'John Doe', 'John Smith', 'Johnson Corp'. "
            "Leave empty to return all names."
        ),
    ),
    entity_type: Optional[str] = Query(
        None,
        description=(
            "Filter by entity type — supports fuzzy matching, no exact spelling needed. "
            "Matching order: (1) exact → 'restaurant', "
            "(2) partial → 'rest', "
            "(3) fuzzy/typo → 'restrunt'. "
            "Default types: home, work, business, other. "
            "Custom types can be added via the Entity Types section. "
            "Leave empty to return all entity types."
        ),
    ),
    # ── radius (optional — defaults to 5.0 km) ───────────────────────────────
    radius: float = Query(
        5.0,
        gt=0,
        description=(
            "Search radius in km (or miles if configured in settings). "
            "Defaults to 5.0 if not provided — "
            "you don't need to specify this for a standard nearby search."
        ),
    ),
    # ── pagination ────────────────────────────────────────────────────────────
    page: int = Query(
        1,
        ge=1,
        description="Page number. Starts at 1. Default: 1.",
    ),
    page_size: int = Query(
        10,
        ge=1,
        le=100,
        description="Number of results per page. Max 100. Default: 10.",
    ),
    service: AddressService = Depends(get_address_service),
) -> PaginatedResponse[AddressOut]:
    """
    Search addresses near a location with optional filters and pagination.
    latitude and longitude are always required.
    entity_name, entity_type and radius are all optional.
    radius defaults to 5.0 km if not provided.
    """
    logger.info(
        f"Route: GET /addresses/search "
        f"lat={latitude} lon={longitude} radius={radius} "
        f"entity_name={entity_name} entity_type={entity_type} "
        f"page={page} page_size={page_size}"
    )
    params = AddressFilterParams(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        entity_name=entity_name,
        entity_type=entity_type,
        page=page,
        page_size=page_size,
    )
    return await service.search_addresses(params)





@router.get(
    "/{address_id}",
    response_model=AddressOut,
    summary="Get a single address",
    description="Retrieve a single address by its ID including full entity type details.",
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





@router.post(
    "/",
    response_model=AddressOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address",
    description=(
        "Create a new address with coordinates.\n\n"

        "---\n\n"

        "### entity_type_id\n"
        "Must reference an existing entity type. "
        "The following types are available by default:\n\n"
        "| ID | Name |\n"
        "|----|------|\n"
        "| 1 | home |\n"
        "| 2 | work |\n"
        "| 3 | business |\n"
        "| 4 | other |\n\n"
        "> **Need a different type?** Scroll down to the **Entity Types** section "
        "in this page and use `POST /entity-types` to create a custom one "
        "(e.g. `restaurant`, `gym`, `hotel`). "
        "Then use the returned `id` here.\n\n"

        "---\n\n"

        "### Coordinates\n"
        "- `latitude` — must be between **-90 and 90**\n"
        "- `longitude` — must be between **-180 and 180**\n"
        "- Tip: use [Google Maps](https://maps.google.com) — right-click any location "
        "and copy the coordinates shown.\n\n"

        "---\n\n"

        "### Optional fields\n"
        "- `state` — province or state, leave empty if not applicable\n"
        "- `postal_code` — zip or postal code\n"
        "- `secondary_address` — apartment, suite, floor, unit number etc.\n"
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





@router.patch(
    "/{address_id}",
    response_model=AddressOut,
    summary="Partially update an address",
    description=(
        "Update only the fields you provide. "
        "Fields not included in the request body are left unchanged.\n\n"
        "This is a **PATCH** — not a full replacement (PUT). "
        "For example, sending only `{ \"city\": \"Amsterdam\" }` "
        "updates just the city and leaves everything else as-is.\n\n"
        "Returns `404` if the address is not found.\n"
        "Returns `404` if the new `entity_type_id` does not exist."
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
    description=(
        "Permanently delete an address by its ID. "
        "This action cannot be undone. "
        "Returns `404` if the address is not found."
    ),
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