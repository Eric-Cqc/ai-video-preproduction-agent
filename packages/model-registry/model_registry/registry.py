from typing import Protocol

from model_registry.capability import ProviderCapability


class ProviderAdapter(Protocol):
    @property
    def capability(self) -> ProviderCapability: ...


class DuplicateProviderError(ValueError):
    """Raised when a provider identifier is registered more than once."""


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        identifier = adapter.capability.identifier
        if identifier in self._adapters:
            raise DuplicateProviderError(f"provider identifier already registered: {identifier}")
        self._adapters[identifier] = adapter

    def get(self, identifier: str) -> ProviderAdapter:
        return self._adapters[identifier]

    def __len__(self) -> int:
        return len(self._adapters)
