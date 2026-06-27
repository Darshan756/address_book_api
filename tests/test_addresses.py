import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.models.address import Base, EntityType
from app.core.database import get_db

# ── test database setup ───────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create tables and seed default entity types before tests run."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        session.add_all([
            EntityType(name="home", is_default=True),
            EntityType(name="work", is_default=True),
        ])
        await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── test 1: create address ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_address():
    """POST /api/v1/addresses/ should create a new address and return 201."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,      # ← fix: follows the 307 redirect
    ) as client:
        response = await client.post(
            "/api/v1/addresses/",   # ← fix: trailing slash
            json={
                "entity_name": "John Doe",
                "entity_type_id": 1,
                "street": "Dam Square 1",
                "city": "Amsterdam",
                "country": "NL",
                "latitude": 52.3731,
                "longitude": 4.8932,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["entity_name"] == "John Doe"
    assert data["city"] == "Amsterdam"
    assert data["latitude"] == 52.3731
    assert data["longitude"] == 4.8932
    assert "id" in data


# ── test 2: fetch address by id ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_address_by_id():
    """GET /api/v1/addresses/{id} should return the correct address."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,      # ← fix: follows the 307 redirect
    ) as client:
        # create first
        create_response = await client.post(
            "/api/v1/addresses/",   # ← fix: trailing slash
            json={
                "entity_name": "Jane Doe",
                "entity_type_id": 1,
                "street": "Kalverstraat 10",
                "city": "Amsterdam",
                "country": "NL",
                "latitude": 52.3702,
                "longitude": 4.8952,
            },
        )
        address_id = create_response.json()["id"]

        # fetch by ID
        response = await client.get(f"/api/v1/addresses/{address_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == address_id
    assert data["entity_name"] == "Jane Doe"
    assert data["city"] == "Amsterdam"