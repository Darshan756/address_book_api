"""
API Dependencies
─────────────────
Wires together the database session, repository, and service
using FastAPI's Depends() system.

Every route that needs the service just declares:
    service: AddressService = Depends(get_address_service)

FastAPI handles the rest automatically —
opens DB session → creates repo → creates service → injects into route.
"""

import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.address_repo import AddressRepository
from app.services.address_service import AddressService

logger = logging.getLogger(__name__)

def get_address_repository(
    db: AsyncSession = Depends(get_db),
) -> AddressRepository:
    """
    Creates an AddressRepository with the current DB session.

    get_db() is a dependency itself — FastAPI resolves it first,
    opens the async session, then passes it here automatically.
    """
    return AddressRepository(db=db)




def get_address_service(
    repo: AddressRepository = Depends(get_address_repository),
) -> AddressService:
    """
    Creates an AddressService with the current repository.

    This is what routes import and use via Depends():

        service: AddressService = Depends(get_address_service)

    The full dependency chain FastAPI resolves automatically:

        get_db()                   → AsyncSession
            ↓
        get_address_repository()   → AddressRepository
            ↓
        get_address_service()      → AddressService
            ↓
        route function             → uses service
    """
    return AddressService(repo=repo)