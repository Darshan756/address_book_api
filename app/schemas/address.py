from pydantic import BaseModel, Field, field_validator
from typing import Optional, Generic, TypeVar


# ─────────────────────────────────────────
# ENTITY TYPE SCHEMAS
# ─────────────────────────────────────────

class EntityTypeBase(BaseModel):
    """Shared fields used by both create and response schemas."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of the address e.g. home, work, business",
    )


class EntityTypeCreate(EntityTypeBase):
    """
    Schema for creating a new entity type via API.
    User only provides the name — is_default is always
    False for user-created types, set in the service layer.
    """
    pass


class EntityTypeOut(EntityTypeBase):
    """
    Schema for returning entity type data in API responses.
    Includes id and is_default so the client knows
    which ones are system defaults vs user-created.
    """
    id: int
    is_default: bool

    # allows ORM model → schema conversion
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
# ADDRESS SCHEMAS
# ─────────────────────────────────────────

class AddressBase(BaseModel):
    """
    Shared fields for address create and update.
    Contains all fields the user can provide.
    """
    entity_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the person or place e.g. John Doe, Acme Corp",
    )
    entity_type_id: int = Field(
        ...,
        description="ID of the entity type — must exist in entity_types table",
    )
    street: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    secondary_address: Optional[str] = Field(
        None,
        max_length=200,
        description="Apartment, suite, floor etc.",
    )

    # coordinates — required by the assessment
    latitude: float = Field(
        ...,
        ge=-90,     # ge = greater than or equal (valid lat range)
        le=90,      # le = less than or equal
        description="Latitude of the address (-90 to 90)",
    )
    longitude: float = Field(
        ...,
        ge=-180,    # valid longitude range
        le=180,
        description="Longitude of the address (-180 to 180)",
    )

    @field_validator("country")
    @classmethod
    def country_must_not_be_blank(cls, v: str) -> str:
        """Ensures country is not just whitespace."""
        if not v.strip():
            raise ValueError("Country cannot be blank")
        return v.strip()

    @field_validator("city")
    @classmethod
    def city_must_not_be_blank(cls, v: str) -> str:
        """Ensures city is not just whitespace."""
        if not v.strip():
            raise ValueError("City cannot be blank")
        return v.strip()


class AddressCreate(AddressBase):
    """
    Schema for creating a new address.
    Inherits all fields from AddressBase.
    All required fields must be provided by the user.
    """
    pass


class AddressUpdate(BaseModel):
    """
    Schema for updating an existing address.
    All fields are optional — only provided fields will be updated.
    This is a PATCH pattern — no need to send all fields.
    """
    entity_name: Optional[str] = Field(None, min_length=1, max_length=100)
    entity_type_id: Optional[int] = None
    street: Optional[str] = Field(None, min_length=1, max_length=200)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    secondary_address: Optional[str] = Field(None, max_length=200)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class AddressOut(AddressBase):
    """
    Schema for returning address data in API responses.
    Includes id and the full entity_type object (not just the id)
    so the client gets all details in one response.
    """
    id: int
    entity_type: EntityTypeOut  # nested — returns full entity type details

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
# PAGINATION
# ─────────────────────────────────────────

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    Works for any list response — addresses, entity types etc.

    Example response:
    {
        "total": 100,
        "page": 1,
        "page_size": 10,
        "pages": 10,
        "results": [...]
    }
    """
    total: int        # total matching records
    page: int         # current page number
    page_size: int    # results per page
    pages: int        # total number of pages
    results: list[T]  # actual data


# ─────────────────────────────────────────
# SEARCH FILTER PARAMS
# ─────────────────────────────────────────

class AddressFilterParams(BaseModel):
    """
    Filter + pagination params for the /search endpoint.

    Required:
        latitude  — user's current location latitude
        longitude — user's current location longitude

    Optional (all default to None / no filter):
        entity_name  — partial match on address name
                       e.g. "john" matches "John Doe", "John Smith"
        entity_type  — fuzzy match on entity type
                       e.g. "resto" matches "restaurant"
        radius       — search radius, defaults to 5.0 km if not provided

    Pagination:
        page      — page number (default 1)
        page_size — results per page (default 10, max 100)

    Examples:
        lat=52.37, lon=4.89
            → all addresses within 5km (default radius)

        lat=52.37, lon=4.89, radius=10
            → all addresses within 10km

        lat=52.37, lon=4.89, entity_type=restaurant
            → restaurants within 5km (default radius)

        lat=52.37, lon=4.89, entity_name=john, radius=20
            → Johns within 20km

        lat=52.37, lon=4.89, entity_name=mc, entity_type=restaurant
            → McDonalds-like restaurants within 5km
    """

    # ── coordinates (always required) ────────────────────────────────────────
    # user must provide their location for distance-based search
    latitude: float = Field(
        ...,        # ... = required, no default
        ge=-90,
        le=90,
        description="Your current location latitude (-90 to 90). Required.",
    )
    longitude: float = Field(
        ...,        # ... = required, no default
        ge=-180,
        le=180,
        description="Your current location longitude (-180 to 180). Required.",
    )

    # ── search filters (all optional) ────────────────────────────────────────
    entity_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description=(
            "Filter by entity name (partial, case insensitive). "
            "'john' matches 'John Doe', 'John Smith'."
        ),
    )
    entity_type: Optional[str] = Field(
        None,
        description=(
            "Filter by entity type (fuzzy match). "
            "'resto' or 'restrunt' both match 'restaurant'."
        ),
    )

    # ── radius (optional — defaults to 5.0 km) ───────────────────────────────
    radius: float = Field(
        5.0,        # default 5km if user does not provide one
        gt=0,
        description=(
            "Search radius in configured unit (km or miles). "
            "Defaults to 5.0 if not provided."
        ),
    )

    # ── pagination ────────────────────────────────────────────────────────────
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        description="Results per page (max 100)",
    )


# kept for backward compatibility with get_nearby_addresses
class NearbySearchParams(BaseModel):
    """
    Schema for the simple nearby search (used internally).
    Prefer AddressFilterParams for the /search endpoint.
    """
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: float = Field(5.0, gt=0)
    entity_type: Optional[str] = Field(None)