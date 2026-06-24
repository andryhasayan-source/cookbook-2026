from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Table, ForeignKey
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

recipe_tags = Table("recipe_tags", Base.metadata,
    Column("recipe_id", Integer, ForeignKey("recipes.id")),
    Column("tag_id",    Integer, ForeignKey("tags.id")))

class Chef(Base):
    __tablename__ = "chefs"
    id             = Column(Integer, primary_key=True)
    name           = Column(String(100), nullable=False)
    country        = Column(String(50))
    michelin_stars = Column(Integer, default=0)
    recipes        = relationship("Recipe", back_populates="chef")

class Recipe(Base):
    __tablename__ = "recipes"
    id              = Column(Integer, primary_key=True)
    title           = Column(String(200), nullable=False)
    chef_id         = Column(Integer, ForeignKey("chefs.id"))
    description     = Column(Text)
    ingredients     = Column(Text)
    instructions    = Column(Text)
    prep_time       = Column(Integer, default=0)
    cook_time       = Column(Integer, default=0)
    total_time      = Column(Integer, default=0)
    difficulty      = Column(String(20))
    cuisine_type    = Column(String(50))
    image_emoji     = Column(String(10), default="🍽")
    image_path      = Column(String(500), default="")
    step_timers     = Column(Text, default="[]")
    rating          = Column(Float, default=0.0)
    rating_count    = Column(Integer, default=0)
    is_user_added   = Column(Boolean, default=False)
    is_favorite     = Column(Boolean, default=False)
    notes           = Column(Text, default="")
    calories_per_serving = Column(Integer, default=0)
    proteins_per_serving = Column(Float,   default=0.0)
    fats_per_serving     = Column(Float,   default=0.0)
    carbs_per_serving    = Column(Float,   default=0.0)
    default_servings     = Column(Integer, default=4)
    cook_count           = Column(Integer, default=0)
    last_cooked          = Column(DateTime, nullable=True)
    created_at           = Column(DateTime, default=datetime.now)
    chef = relationship("Chef", back_populates="recipes")
    tags = relationship("Tag", secondary=recipe_tags)

class Tag(Base):
    __tablename__ = "tags"
    id      = Column(Integer, primary_key=True)
    name    = Column(String(50), unique=True)

class MealPlan(Base):
    __tablename__ = "meal_plans"
    id          = Column(Integer, primary_key=True)
    recipe_id   = Column(Integer, ForeignKey("recipes.id"))
    day_of_week = Column(Integer)
    meal_type   = Column(String(20))
    week_offset = Column(Integer, default=0)
    recipe      = relationship("Recipe")

class ShoppingItem(Base):
    __tablename__ = "shopping_items"
    id            = Column(Integer, primary_key=True)
    text          = Column(String(300))
    checked       = Column(Boolean, default=False)
    source_recipe = Column(String(200), default="")
    created_at    = Column(DateTime, default=datetime.now)
