"""Version 1 API response schemas."""

from pydantic import BaseModel, ConfigDict


class ApiMetadataResponse(BaseModel):
    """Public metadata returned by the StackSense API."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
