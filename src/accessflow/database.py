from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from accessflow.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

Sessionlocal = sessionmaker(bind=engine, autoflush=False, autocommit=False,)

class Base(DeclarativeBase):
    pass