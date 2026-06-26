from pydantic import BaseModel, Field , field_validator
from typing import Optional,Generic, TypeVar

# ENTITY TYPE SCHEMAS

class EntityTypeBase(BaseModel):
    """Shared fields used by both create and response schemas."""
    name: str = Field(
        ...,                       
        min_length=1,
        max_length=100,
        description="Type of the address e.g. home, work, business"
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

    model_config = {"from_attributes": True} 

# ADDRESS SCHEMAS



class AddressBase(BaseModel):
    """
    Shared fields for address create and update.
    Contains all fields the user can provide.
    """
    entity_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the person or place e.g. John Doe, Acme Corp"
    )
    entity_type_id: int = Field(
        ...,
        description="ID of the entity type — must exist in entity_types table"
    )
    street: str = Field(..., min_length=1, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    secondary_address: Optional[str] = Field(
        None,
        max_length=200,
        description="Apartment, suite, floor etc."
    )

    # coordinates — required by the assessment
    latitude: float = Field(
        ...,
        ge=-90,     # ge = greater than or equal (valid lat range)
        le=90,      # le = less than or equal
        description="Latitude of the address between -90 and 90"
    )
    longitude: float = Field(
        ...,
        ge=-180,    # valid longitude range
        le=180,
        description="Longitude of the address between -180 and 180"
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
    This is a PATCH pattern, not PUT (no need to send all fields).
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
    entity_type: EntityTypeOut     # nested — returns full entity type details

    model_config = {"from_attributes": True}

# DISTANCE SEARCH SCHEMA




class NearbySearchParams(BaseModel):
    """
    Schema for the distance-based address search.
    Supports filtering by radius and optionally by entity type name.

    Examples:
        - all addresses within 10km
        - restaurants within 5km
        - businesses within 20miles
    """
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: float = Field(
        ...,
        gt=0,
        description="Search radius in configured unit km "
    )
    entity_type: Optional[str] = Field(
        None,
        description="Filter by entity type name e.g. restaurant, home, work"
    )




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
    total: int                  # total matching records
    page: int                   # current page number
    page_size: int              # results per page
    pages: int                  # total number of pages
    results: list[T]            # actual data





class AddressFilterParams(BaseModel):
    """
    All possible filter + pagination params for address search.

    Location coordinates are always required.
    Radius defaults to 5km if not provided.

    Examples:
        ?latitude=52.37&longitude=4.89
            → all addresses within 5km (default radius)
        ?latitude=52.37&longitude=4.89&radius=10
            → all addresses within 10km
        ?entity_type=restaurant&latitude=52.37&longitude=4.89
            → restaurants within 5km
        ?name=john&latitude=52.37&longitude=4.89&radius=20
            → Johns within 20km
    """
    # search filters
    name: Optional[str] = Field(
        None,
        description="Partial name match. 'john' matches 'John Doe', 'John Smith'",
    )
    entity_type: Optional[str] = Field(
        None,
        description="Fuzzy type match. 'resto' matches 'restaurant'",
    )

    # coordinates — always required
    latitude: float = Field(
        ...,                # ... = required, no default
        ge=-90,
        le=90,
        description="Your current location latitude (-90 to 90). Required.",
    )
    longitude: float = Field(
        ...,                # ... = required, no default
        ge=-180,
        le=180,
        description="Your current location longitude (-180 to 180). Required.",
    )

    # radius — optional, defaults to 5km
    radius: float = Field(
        5.0,                # default 5km
        gt=0,
        description=(
            "Search radius in configured unit (km or miles). "
            "Defaults to 5km if not provided."
        ),
    )

    # pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(
        10,
        ge=1,
        le=100,
        description="Results per page (max 100)",
    )