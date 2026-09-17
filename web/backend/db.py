"""SQLite persistence (users + saved projects)."""
from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy import Column, Float, ForeignKey, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("CHROMPEAK_DB", os.path.join(BASE_DIR, "chrompeak.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    projects = relationship("Project", back_populates="owner",
                            cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    algo_params = Column(Text, default="{}")        # JSON: {alg: {param: value}}
    algorithms = Column(Text, default="[]")          # JSON: [alg names]
    x_data = Column(Text)                            # JSON-encoded x array
    y_data = Column(Text)                            # JSON-encoded y array
    results = Column(Text, default="{}")             # JSON: {alg: [peaks]}
    created_at = Column(Float, default=0.0)
    owner = relationship("User", back_populates="projects")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
