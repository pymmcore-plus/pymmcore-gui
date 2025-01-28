from typing import Any
from weakref import WeakValueDictionary

from useq import MDAEvent, MDASequence

_HANDLER_CACHE: WeakValueDictionary[int, Any] = WeakValueDictionary()
HANDLER_META_KEY = "some-handler-key"


def get_handler(obj: int | MDAEvent | MDASequence) -> Any | None:
    """Get handler for id."""
    if isinstance(obj, MDAEvent):
        if obj.sequence is None:
            return None
        obj = obj.sequence

    if isinstance(obj, MDASequence):
        key = obj.metadata.get(HANDLER_META_KEY, None)
    else:
        key = obj
    return _HANDLER_CACHE.get(key)


def store_handler(handler: Any) -> int:
    key = id(handler)
    _HANDLER_CACHE[key] = handler
    return key
