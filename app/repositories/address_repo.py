"""
Address Repository
───────────────────
All database queries for Address and EntityType live here.
No business rules, no HTTP exceptions — only raw SQL.
Business logic lives in the service layer.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.address import Address, EntityType
from app.schemas.address import AddressCreate, AddressUpdate

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

    
    
    # ─────────────────────────────────────────
    # ENTITY TYPE QUERIES
    # ─────────────────────────────────────────

    async def get_all_entity_types(self) -> list[EntityType]:
        """Fetch all entity types ordered by name."""
        logger.debug("Repo: fetching all entity types")
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
        logger.debug(f"Repo: fetching entity type id={entity_type_id}")
        result = await self.db.execute(
            select(EntityType).where(EntityType.id == entity_type_id)
        )
        return result.scalar_one_or_none()

    
    
    
    async def get_entity_type_by_name(self, name: str) -> EntityType | None:
        """
        Fetch a single entity type by name.
        Used to check for duplicates before creating a new one.
        """
        logger.debug(f"Repo: fetching entity type name={name}")
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
        logger.info(f"Repo: creating entity type name={name}")
        entity_type = EntityType(
            name=name.lower(),  # always store lowercase for consistency
            is_default=False,   # user-created types are never defaults
        )
        self.db.add(entity_type)
        await self.db.flush()   # get generated id without committing
        await self.db.refresh(entity_type)
        logger.info(f"Repo: entity type created id={entity_type.id}")
        return entity_type

    
    
    
    async def delete_entity_type(self, entity_type: EntityType) -> None:
        """
        Delete an entity type.
        The service layer checks is_default before calling this —
        default types are never deleted.
        """
        logger.info(
            f"Repo: deleting entity type "
            f"id={entity_type.id} name={entity_type.name}"
        )
        await self.db.delete(entity_type)
        await self.db.flush()

   
   
   
    # ─────────────────────────────────────────
    # ADDRESS QUERIES
    # ─────────────────────────────────────────

    
    
    
    async def get_all_addresses(self) -> list[Address]:
        """
        Fetch all addresses with their entity_type eagerly loaded.
        selectinload avoids the N+1 query problem — instead of
        one query per address to fetch entity_type, it does 2 queries total.
        """
        logger.debug("Repo: fetching all addresses")
        result = await self.db.execute(
            select(Address).options(
                selectinload(Address.entity_type)
            )
        )
        return list(result.scalars().all())

    
    
    
    
    async def get_address_by_id(self, address_id: int) -> Address | None:
        """
        Fetch a single address by ID with entity_type eagerly loaded.
        Returns None if not found.
        """
        logger.debug(f"Repo: fetching address id={address_id}")
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
        logger.info(
            f"Repo: creating address "
            f"entity_name={data.entity_name} city={data.city}"
        )
        address = Address(**data.model_dump())
        self.db.add(address)
        await self.db.flush()

        # refresh with entity_type loaded so the response
        # includes the full entity_type object not just its id
        await self.db.refresh(address, ["entity_type"])
        logger.info(f"Repo: address created id={address.id}")
        return address

    
    
    
    
    async def update_address(self, address: Address, data: AddressUpdate) -> Address:
        """
        Update only the fields provided in data (PATCH behaviour).
        exclude_unset=True means fields the user did not send
        are completely ignored — existing values are preserved.
        """
        logger.info(f"Repo: updating address id={address.id}")
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(address, field, value)

        await self.db.flush()
        await self.db.refresh(address, ["entity_type"])
        logger.info(
            f"Repo: address updated "
            f"id={address.id} fields={list(update_data.keys())}"
        )
        return address

    
    
    
    
    async def delete_address(self, address: Address) -> None:
        """Delete an address row."""
        logger.info(f"Repo: deleting address id={address.id}")
        await self.db.delete(address)
        await self.db.flush()

    
    
    
    async def get_all_addresses_with_coordinates(self) -> list[Address]:
        """
        Fetch all addresses that have valid coordinates.
        Used by the simple nearby search — distance filtered
        in Python using haversine because SQLite has no
        native geospatial functions.
        """
        logger.debug("Repo: fetching all addresses with coordinates")
        result = await self.db.execute(
            select(Address)
            .options(selectinload(Address.entity_type))
            .where(
                Address.latitude.is_not(None),
                Address.longitude.is_not(None),
            )
        )
        return list(result.scalars().all())

    # ─────────────────────────────────────────
    # FILTERED SEARCH QUERY
    # ─────────────────────────────────────────

    
    
    async def get_filtered_addresses(
        self,
        entity_name: Optional[str] = None,
        entity_type_name: Optional[str] = None,
    ) -> list[Address]:
        """
        Fetch addresses filtered at SQL level by entity name
        and/or entity type name.

        Why filter name and type in SQL but distance in Python?
        ─────────────────────────────────────────────────────────
        Name and type are simple string comparisons — SQL handles
        these efficiently with ILIKE and JOIN.
        Distance requires haversine math — SQLite has no geospatial
        functions so we filter coordinates in Python after fetching.

        Args:
            entity_name:      partial case insensitive match on entity_name
                              e.g. "john" matches "John Doe", "John Smith"
            entity_type_name: exact entity type name to filter by
                              (fuzzy resolution already done in service layer)
        """
        logger.debug(
            f"Repo: get_filtered_addresses "
            f"entity_name={entity_name} entity_type={entity_type_name}"
        )

        query = (
            select(Address)
            .options(selectinload(Address.entity_type))
            .join(Address.entity_type)  # join entity_types table for type filter
        )

        # filter by entity name — partial case insensitive match
        # "john" matches "John Doe", "John Smith", "Johnson Corp"
        if entity_name:
            query = query.where(
                Address.entity_name.ilike(f"%{entity_name}%")
            )

        # filter by entity type name — exact match
        # fuzzy resolution already done in service layer
        # so by the time we get here it's already "restaurant" not "resto"
        if entity_type_name:
            query = query.where(
                EntityType.name == entity_type_name.lower()
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())