"""
Address Service Layer
─────────────────────
Contains all business logic for addresses and entity types.
No HTTP or SQLAlchemy details here — all DB access goes
through the repository, all HTTP exceptions are raised here.
"""

import logging
from math import radians, sin, cos, sqrt, atan2

from fastapi import HTTPException, status
from app.repositories.address_repo import AddressRepository

from app.schemas.address import (
    AddressCreate,
    AddressUpdate,
    EntityTypeCreate,
    NearbySearchParams,
)

from app.models.address import Address, EntityType
from app.core.config import settings

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
    
     # ENTITY TYPE BUSINESS LOGIC

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
            logger.warning(f"Service: entity type already exists name={data.name}")
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
            logger.warning(f"Service: entity type not found id={entity_type_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity type with id {entity_type_id} not found",
            )

        # rule: default types are protected from deletion
        # is_default=True means seeded via migration, not user-created
        if entity_type.is_default:
            logger.warning(
                f"Service: attempted to delete default "
                f"entity type id={entity_type_id} name={entity_type.name}"
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
    
    # ADDRESS BUSINESS LOGIC

    async def get_all_addresses(self) -> list[Address]:
        """Return all addresses. No rules needed here."""
        logger.debug("Service: fetching all addresses")
        return await self.repo.get_all_addresses()
    

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
            - coordinate validation is handled by Pydantic schema
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
    
    # DISTANCE SEARCH
    # core feature of the assessment


    async def get_nearby_addresses(
        self,
        params: NearbySearchParams,
    ) -> list[Address]:
        """
        Find all addresses within a given radius from a coordinate point.

        Why Haversine and not Euclidean (straight line) distance?
        ───────────────────────────────────────────────────────────
        Earth is a sphere. Treating lat/lon as flat X/Y coordinates
        introduces significant error, especially at larger distances
        or near the poles. Haversine accounts for Earth's curvature
        and returns accurate real-world distances.

        Why filter in Python and not SQL?
        ────────────────────────────────
        SQLite has no native geospatial extension. In a production
        setup with PostgreSQL + PostGIS you would do this filtering
        directly in SQL with ST_DWithin() for better performance.

        Rules:
            - radius must be > 0 (enforced by Pydantic schema)
            - distance unit (km or miles) is set in config
        """
        logger.info(
            f"Service: nearby search "
            f"lat={params.latitude} lon={params.longitude} "
            f"radius={params.radius} {settings.DEFAULT_DISTANCE_UNIT}"
        )

        # fetch all addresses that have valid coordinates
        all_addresses = await self.repo.get_all_addresses_with_coordinates()

        # filter in Python using haversine formula
        nearby = [
            address for address in all_addresses
            if self._haversine(
                origin_lat=params.latitude,
                origin_lon=params.longitude,
                target_lat=address.latitude,
                target_lon=address.longitude,
            ) <= params.radius
        ]

        logger.info(
            f"Service: found {len(nearby)} addresses within "
            f"{params.radius} {settings.DEFAULT_DISTANCE_UNIT}"
        )
        return nearby
        
    
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
    

    def _haversine(
        self,
        origin_lat: float,
        origin_lon: float,
        target_lat: float,
        target_lon: float,
    ) -> float:
        """
        Calculate the great-circle distance between two points on Earth.

        Formula:
            a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
            c = 2 × atan2(√a, √(1−a))
            d = R × c

        Where:
            Δlat = difference in latitudes
            Δlon = difference in longitudes
            R    = Earth's radius (6371 km or 3956 miles)

        Args:
            origin_lat: latitude of the search origin point
            origin_lon: longitude of the search origin point
            target_lat: latitude of the address being checked
            target_lon: longitude of the address being checked

        Returns:
            Distance in the unit configured in settings
            (km by default, miles if DEFAULT_DISTANCE_UNIT=miles)
        """
        # select earth radius based on configured distance unit
        earth_radius = (
            3956.0                          # miles
            if settings.DEFAULT_DISTANCE_UNIT == "miles"
            else 6371.0                     # kilometres (default)
        )

        # convert all degree values to radians
        # trig functions (sin, cos) require radians not degrees
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