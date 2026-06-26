import logging
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.address import Address, EntityType
from app.schemas.address import AddressCreate, AddressUpdate

# get a logger for this module
# logs will show as "app.repositories.address_repo" in the log output
logger = logging.getLogger(__name__)

class AddressRepository:
    """
    Handles all database operations for Address and EntityType.
    No business rules here — only raw SQL queries.
    Business rules live in the service layer.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Receives the DB session via dependency injection.
        Never create a session inside the repo — always inject it.
        This makes the repo testable with a mock session.
        """
        self.db = db

    async def get_all_entity_types(self) -> list[EntityType]:
        """Fetch all entity types ordered by name."""
        logger.debug("Fetching all entity types")
        result = await self.db.execute(
            select(EntityType).order_by(EntityType.name)
        )
        return list(result.scalars().all())
    
    async def get_entity_type_by_id(self, entity_type_id: int) -> EntityType | None:
        """
        Fetch a single entity type by its ID.
        Returns None if not found — the service layer
        decides what to do with a None (raise 404 etc).
        """
        logger.debug(f"Fetching entity type with id={entity_type_id}")
        result = await self.db.execute(
            select(EntityType).where(EntityType.id == entity_type_id)
        )
        return result.scalar_one_or_none()
    
    async def get_entity_type_by_name(self, name: str) -> EntityType | None:
        """
        Fetch a single entity type by name.
        Used to check for duplicates before creating a new one.
        """
        logger.debug(f"Fetching entity type with name={name}")
        result = await self.db.execute(
            select(EntityType).where(EntityType.name == name.lower())
        )
        return result.scalar_one_or_none()
    
    async def create_entity_type(self, name: str) -> EntityType:
        """
        Create a new user-defined entity type.
        is_default is always False for user-created types —
        only migration-seeded types have is_default=True.
        """
        logger.info(f"Creating new entity type: name={name}")
        entity_type = EntityType(
            name=name.lower(),      # always store lowercase for consistency
            is_default=False,       # user-created types are never defaults
        )
        self.db.add(entity_type)
        await self.db.flush()       # flush to get the generated id without committing
        await self.db.refresh(entity_type)
        logger.info(f"Entity type created: id={entity_type.id}")
        return entity_type
    
    async def delete_entity_type(self, entity_type: EntityType) -> None:
        """
        Delete an entity type.
        The service layer checks is_default before calling this —
        default types are never deleted.
        """
        logger.info(f"Deleting entity type: id={entity_type.id} name={entity_type.name}")
        await self.db.delete(entity_type)
        await self.db.flush()

    async def get_all_addresses(self) -> list[Address]:
        """
        Fetch all addresses with their entity_type eagerly loaded.
        selectinload avoids the N+1 query problem — instead of
        one query per address to fetch entity_type, it does 2 queries total.
        """
        logger.debug("Fetching all addresses")
        result = await self.db.execute(
            select(Address).options(
                selectinload(Address.entity_type)  # eager load related entity_type
            )
        )
        return list(result.scalars().all())
    
    async def get_address_by_id(self, address_id: int) -> Address | None:
        """
        Fetch a single address by ID with entity_type eagerly loaded.
        Returns None if not found.
        """
        logger.debug(f"Fetching address with id={address_id}")
        result = await self.db.execute(
            select(Address)
            .options(selectinload(Address.entity_type))
            .where(Address.id == address_id)
        )
        return result.scalar_one_or_none()
    
    async def create_address(self, data: AddressCreate) -> Address:
        """
        Insert a new address row.
        All validation and rule checks happen in the service
        before this method is called.
        """
        logger.info(f"Creating address: entity_name={data.entity_name} city={data.city}")
        address = Address(**data.model_dump())
        self.db.add(address)
        await self.db.flush()

        # refresh with entity_type loaded so the response
        # includes the full entity_type object not just its id
        await self.db.refresh(address, ["entity_type"])
        logger.info(f"Address created: id={address.id}")
        return address
    
    async def update_address(self, address: Address, data: AddressUpdate) -> Address:
        """
        Update only the fields provided in data (PATCH behaviour).
        exclude_unset=True means fields the user did not send
        are completely ignored — existing values are preserved.
        """
        logger.info(f"Updating address: id={address.id}")
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(address, field, value)

        await self.db.flush()
        await self.db.refresh(address, ["entity_type"])
        logger.info(f"Address updated: id={address.id} fields={list(update_data.keys())}")
        return address
    
    async def delete_address(self, address: Address) -> None:
        """Delete an address row."""
        logger.info(f"Deleting address: id={address.id}")
        await self.db.delete(address)
        await self.db.flush()

# DISTANCE SEARCH

    async def get_all_addresses_with_coordinates(self) -> list[Address]:
        """
        Fetch all addresses that have valid coordinates.
        Used by the distance search — we filter by distance
        in Python using the haversine formula rather than in SQL,
        because SQLite has no native geospatial functions.
        """
        logger.debug("Fetching all addresses with coordinates for distance search")
        result = await self.db.execute(
            select(Address)
            .options(selectinload(Address.entity_type))
            .where(
                Address.latitude.is_not(None),
                Address.longitude.is_not(None),
            )
        )
        return list(result.scalars().all())