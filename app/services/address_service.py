"""
Address Service Layer
─────────────────────
Contains all business logic for addresses and entity types.
No HTTP or SQLAlchemy details here — all DB access goes
through the repository, all HTTP exceptions are raised here.
"""

import logging
from difflib import SequenceMatcher
from math import atan2, cos, radians, sin, sqrt
from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.address import Address, EntityType
from app.repositories.address_repo import AddressRepository
from app.schemas.address import (
    AddressCreate,
    AddressFilterParams,
    AddressOut,
    AddressUpdate,
    EntityTypeCreate,
    PaginatedResponse,
)

# module-level logger
# logs appear as "app.services.address_service" in output
logger = logging.getLogger(__name__)


class AddressService:
    """
    Handles all business rules for addresses and entity types.

    Injected dependencies:
        repo: AddressRepository — all DB queries go through here

    Never instantiated directly in routes —
    always injected via FastAPI's Depends() in api/deps.py.
    """

    def __init__(self, repo: AddressRepository) -> None:
        self.repo = repo

    # ─────────────────────────────────────────
    # ENTITY TYPE BUSINESS LOGIC
    # ─────────────────────────────────────────

    async def get_all_entity_types(self) -> list[EntityType]:
        """Return all entity types. No rules needed here."""
        logger.debug("Service: fetching all entity types")
        return await self.repo.get_all_entity_types()

    async def create_entity_type(self, data: EntityTypeCreate) -> EntityType:
        """
        Create a new user-defined entity type.

        Rules:
            - name must be unique (case insensitive)
            - name is always stored lowercase
        """
        logger.info(f"Service: creating entity type name={data.name}")

        # rule: check duplicate name (case insensitive)
        existing = await self.repo.get_entity_type_by_name(data.name.lower())
        if existing:
            logger.warning(
                f"Service: entity type already exists name={data.name}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Entity type '{data.name}' already exists",
            )

        return await self.repo.create_entity_type(data.name)

    async def delete_entity_type(self, entity_type_id: int) -> None:
        """
        Delete a user-defined entity type.

        Rules:
            - must exist
            - default types (home, work, business, other)
              are protected and cannot be deleted
        """
        logger.info(f"Service: deleting entity type id={entity_type_id}")

        # rule: must exist
        entity_type = await self.repo.get_entity_type_by_id(entity_type_id)
        if not entity_type:
            logger.warning(
                f"Service: entity type not found id={entity_type_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity type with id {entity_type_id} not found",
            )

        # rule: default types are protected from deletion
        # is_default=True means seeded via migration, not user-created
        if entity_type.is_default:
            logger.warning(
                f"Service: attempted to delete default entity type "
                f"id={entity_type_id} name={entity_type.name}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Cannot delete default entity type '{entity_type.name}'. "
                    f"Default types are protected."
                ),
            )

        await self.repo.delete_entity_type(entity_type)
        logger.info(f"Service: entity type deleted id={entity_type_id}")

    # ─────────────────────────────────────────
    # ADDRESS BUSINESS LOGIC
    # ─────────────────────────────────────────

    async def get_address_by_id(self, address_id: int) -> Address:
        """
        Fetch a single address by ID.

        Rules:
            - must exist
        """
        logger.debug(f"Service: fetching address id={address_id}")

        address = await self.repo.get_address_by_id(address_id)
        if not address:
            logger.warning(f"Service: address not found id={address_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Address with id {address_id} not found",
            )

        return address

    async def create_address(self, data: AddressCreate) -> Address:
        """
        Create a new address.

        Rules:
            - entity_type_id must reference an existing entity type
            - coordinate validation handled by Pydantic schema
              (latitude -90 to 90, longitude -180 to 180)
        """
        logger.info(
            f"Service: creating address "
            f"entity_name={data.entity_name} city={data.city}"
        )

        # rule: entity_type must exist before creating address
        await self._validate_entity_type(data.entity_type_id)

        address = await self.repo.create_address(data)
        logger.info(f"Service: address created id={address.id}")
        return address

    async def update_address(
        self,
        address_id: int,
        data: AddressUpdate,
    ) -> Address:
        """
        Partially update an existing address (PATCH behaviour).
        Only fields provided in the request body are updated.
        Fields not sent by the client are left unchanged.

        Rules:
            - address must exist
            - if entity_type_id is changing it must exist
        """
        logger.info(f"Service: updating address id={address_id}")

        # rule: address must exist
        address = await self.get_address_by_id(address_id)

        # rule: only validate entity_type if it is being changed
        if data.entity_type_id is not None:
            await self._validate_entity_type(data.entity_type_id)

        updated = await self.repo.update_address(address, data)
        logger.info(f"Service: address updated id={address_id}")
        return updated

    async def delete_address(self, address_id: int) -> None:
        """
        Delete an address.

        Rules:
            - must exist
        """
        logger.info(f"Service: deleting address id={address_id}")

        # rule: must exist — get_address_by_id raises 404 if not found
        address = await self.get_address_by_id(address_id)
        await self.repo.delete_address(address)
        logger.info(f"Service: address deleted id={address_id}")

    # ─────────────────────────────────────────
    # UNIFIED SEARCH — core assessment feature
    # ─────────────────────────────────────────

    async def search_addresses(
        self,
        params: AddressFilterParams,
    ) -> PaginatedResponse[AddressOut]:
        """
        Unified search — handles all combinations of:
            - name filter     (partial SQL match)
            - entity type     (fuzzy resolved → exact SQL match)
            - distance filter (haversine in Python)
            - pagination      (slice final results)

        Filter order (cheapest to most expensive):
            1. Resolve fuzzy entity type → exact name
            2. SQL filters: name + entity type  → reduces dataset early
            3. Python distance filter           → haversine on reduced set
            4. Pagination                       → slice final results

        Examples:
            ?name=john                              → all Johns
            ?entity_type=resto                      → all restaurants
            ?entity_type=restaurant&radius=10       → restaurants within 10km
            ?name=mcdonalds&entity_type=restaurant  → combined
            ?page=2&page_size=5                     → paginated
        """
        logger.info(
            f"Service: search addresses "
            f"name={params.name} entity_type={params.entity_type} "
            f"lat={params.latitude} lon={params.longitude} "
            f"radius={params.radius} "
            f"page={params.page} page_size={params.page_size}"
        )

        # step 1: resolve fuzzy entity type search to exact stored name
        # "resto"    → "restaurant"
        # "restrunt" → "restaurant" (typo tolerance)
        # "home"     → "home"
        resolved_entity_type = None
        if params.entity_type:
            resolved_entity_type = await self._resolve_entity_type(
                params.entity_type
            )
            if not resolved_entity_type:
                # no entity type matched — return empty response immediately
                logger.info(
                    f"Service: no entity type matched '{params.entity_type}'"
                )
                return PaginatedResponse(
                    total=0,
                    page=params.page,
                    page_size=params.page_size,
                    pages=0,
                    results=[],
                )

        # step 2: fetch from DB with SQL-level name + type filters
        # reduces the dataset before the expensive Python distance check
        addresses = await self.repo.get_filtered_addresses(
            name=params.name,
            entity_type_name=resolved_entity_type,
        )
        logger.debug(
            f"Service: {len(addresses)} addresses after SQL filters"
        )

        # step 3: apply distance filter in Python using haversine
        # only activates when all three coords are provided together
        
        addresses = [
                address for address in addresses
                if self._haversine(
                    origin_lat=params.latitude,
                    origin_lon=params.longitude,
                    target_lat=address.latitude,
                    target_lon=address.longitude,
                ) <= params.radius
            ]
        logger.debug(
                f"Service: {len(addresses)} addresses after distance filter "
                f"({params.radius} {settings.DEFAULT_DISTANCE_UNIT})"
            )

        # step 4: paginate the final filtered list
        total = len(addresses)
        pages = max(1, -(-total // params.page_size))  # ceiling division
        start = (params.page - 1) * params.page_size
        end = start + params.page_size
        paginated = addresses[start:end]

        logger.info(
            f"Service: returning page {params.page}/{pages} "
            f"({len(paginated)} of {total} results)"
        )

        return PaginatedResponse(
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=pages,
            results=paginated,
        )

    # ─────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────

    async def _validate_entity_type(self, entity_type_id: int) -> None:
        """
        Reusable guard — raises HTTP 404 if entity type does not exist.
        Called by create_address and update_address to avoid
        duplicating the same existence check in both methods.
        """
        entity_type = await self.repo.get_entity_type_by_id(entity_type_id)
        if not entity_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity type with id {entity_type_id} not found",
            )

    async def _resolve_entity_type(self, search: str) -> Optional[str]:
        """
        Resolve a fuzzy entity type search term to an exact stored name.

        Tries in order:
            1. Exact match   "restaurant" → "restaurant"
            2. Partial match "rest"       → "restaurant"
            3. Fuzzy match   "restrunt"   → "restaurant" (≥60% similarity)

        Returns the matched entity type name or None if no match found.
        """
        all_types = await self.repo.get_all_entity_types()
        search_lower = search.lower()

        # 1. exact match — fastest, check first
        for et in all_types:
            if et.name == search_lower:
                logger.debug(
                    f"Entity type exact match: '{search}' → '{et.name}'"
                )
                return et.name

        # 2. partial match — "rest" in "restaurant"
        for et in all_types:
            if search_lower in et.name or et.name in search_lower:
                logger.debug(
                    f"Entity type partial match: '{search}' → '{et.name}'"
                )
                return et.name

        # 3. fuzzy match using difflib SequenceMatcher
        # handles typos like "restrunt" → "restaurant"
        best_match = None
        best_ratio = 0.0
        for et in all_types:
            ratio = SequenceMatcher(None, search_lower, et.name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = et.name

        if best_ratio >= 0.6:
            logger.debug(
                f"Entity type fuzzy match: '{search}' → '{best_match}' "
                f"ratio={best_ratio:.2f}"
            )
            return best_match

        logger.debug(
            f"Entity type no match: '{search}' "
            f"best_ratio={best_ratio:.2f} below threshold=0.6"
        )
        return None

    def _haversine(
        self,
        origin_lat: float,
        origin_lon: float,
        target_lat: float,
        target_lon: float,
    ) -> float:
        """
        Calculate the great-circle distance between two points on Earth.

        Why Haversine and not Euclidean (straight line) distance?
        ──────────────────────────────────────────────────────────
        Earth is a sphere. Treating lat/lon as flat X/Y coordinates
        introduces significant error especially at larger distances
        or near the poles. Haversine accounts for Earth's curvature
        and returns accurate real-world distances.

        Formula:
            a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
            c = 2 × atan2(√a, √(1−a))
            d = R × c

        Where:
            Δlat = difference in latitudes (radians)
            Δlon = difference in longitudes (radians)
            R    = Earth's radius (6371 km or 3956 miles)

        Args:
            origin_lat: latitude of the search origin point
            origin_lon: longitude of the search origin point
            target_lat: latitude of the address being checked
            target_lon: longitude of the address being checked

        Returns:
            Distance in the unit set in config (km or miles)
        """
        # select earth radius based on configured distance unit
        earth_radius = (
            3956.0  # miles
            if settings.DEFAULT_DISTANCE_UNIT == "miles"
            else 6371.0  # kilometres (default)
        )

        # convert degrees to radians — trig functions require radians
        lat1 = radians(origin_lat)
        lat2 = radians(target_lat)
        delta_lat = radians(target_lat - origin_lat)
        delta_lon = radians(target_lon - origin_lon)

        # haversine formula
        a = (
            sin(delta_lat / 2) ** 2
            + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = earth_radius * c

        logger.debug(
            f"Haversine: ({origin_lat},{origin_lon}) → "
            f"({target_lat},{target_lon}) = "
            f"{distance:.2f} {settings.DEFAULT_DISTANCE_UNIT}"
        )

        return distance