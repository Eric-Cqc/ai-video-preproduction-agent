from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    modalities: frozenset[Literal["text", "image", "audio", "video"]]
    asynchronous: bool
