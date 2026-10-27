"""Maps a provider name (stored on each connection) to its implementation.

To add a data source, implement Provider (see base.py) and add it to _PROVIDERS.
"""

from app.core.errors import AppError
from app.providers.base import Provider
from app.providers.simplefin.provider import SimpleFINProvider

_PROVIDERS: dict[str, type[Provider]] = {
    SimpleFINProvider.name: SimpleFINProvider,
}


def get_provider(name: str) -> Provider:
    try:
        return _PROVIDERS[name]()
    except KeyError as exc:
        raise AppError(f"Unknown provider: {name}") from exc
