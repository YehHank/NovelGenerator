import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class HookStatus(str, enum.Enum):
    active = "active"
    referenced = "referenced"
    resolved = "resolved"


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    genre = Column(String(100), default="")
    world_setting = Column(Text, default="")
    writing_style = Column(Text, default="")
    auto_generate = Column(Boolean, default=False)
    auto_interval_sec = Column(Integer, default=300)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    episodes = relationship("Episode", back_populates="story", order_by="Episode.episode_number")
    characters = relationship("Character", back_populates="story")
    plot_hooks = relationship("PlotHook", back_populates="story")


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(200), default="")
    content = Column(Text, nullable=False)
    summary = Column(Text, default="")
    direction_hint = Column(Text, default="")
    audio_path = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    story = relationship("Story", back_populates="episodes")


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    current_state = Column(JSON, default=dict)
    traits = Column(JSON, default=dict)
    relationship_map = Column(JSON, default=dict)

    story = relationship("Story", back_populates="characters")


class PlotHook(Base):
    __tablename__ = "plot_hooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    description = Column(Text, nullable=False)
    planted_episode = Column(Integer, default=0)
    referenced_episodes = Column(JSON, default=list)
    status = Column(SAEnum(HookStatus, native_enum=False), default=HookStatus.active)

    story = relationship("Story", back_populates="plot_hooks")
