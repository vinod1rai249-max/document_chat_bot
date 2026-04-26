from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings
from app.services.blob_persistence import BlobPersistence


settings = get_settings()
blob_persistence = BlobPersistence()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    if blob_persistence.enabled:
        engine.dispose()
        blob_persistence.sync_down()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
