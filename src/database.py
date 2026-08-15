import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# On Vercel, force writable /tmp SQLite unless a valid external SQLite is specified.
raw_db_url = os.getenv("DATABASE_URL", "")
if os.getenv("VERCEL"):
    if raw_db_url.startswith("sqlite"):
        DATABASE_URL = raw_db_url
    else:
        DATABASE_URL = "sqlite:////tmp/onboardops.db"
else:
    DATABASE_URL = raw_db_url if raw_db_url else "sqlite:///./onboardops.db"

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
