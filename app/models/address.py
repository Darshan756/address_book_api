from sqlalchemy import (
    String,
    Boolean,
    Float,
    ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import DeclarativeBase




class Base(DeclarativeBase):
    pass





class EntityType(Base):
    __tablename__ = "entity_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    addresses: Mapped[list["Address"]] = relationship(
        "Address",
        back_populates="entity_type"
    )

    def __repr__(self) -> str:
        return f"<EntityType(id={self.id}, name={self.name})>"




class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)

    entity_type_id: Mapped[int] = mapped_column(
        ForeignKey("entity_types.id"),
        nullable=False
    )

    entity_type: Mapped["EntityType"] = relationship(
        "EntityType",
        back_populates="addresses"
    )

    street: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    secondary_address: Mapped[str | None] = mapped_column(String(200), nullable=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Address(id={self.id}, entity_name={self.entity_name}, "
            f"city={self.city}, country={self.country})>"
        )