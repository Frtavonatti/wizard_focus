from pydantic import BaseModel, ConfigDict


class BaseRead(BaseModel):
    """Base for all Read schemas — enables ORM mode and UUID serialization."""

    model_config = ConfigDict(from_attributes=True)
