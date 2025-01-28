import builtins
from collections.abc import Callable
from typing import Any, Generic, TypeVar, overload

from PyQt6.QtCore import QObject, pyqtSignal
from typing_extensions import Self

QO = TypeVar("QO", bound=QObject)
V = TypeVar("V")

class pyqtProperty(property, Generic[V]):
    """A property that integrates Python and Qt properties."""

    def __init__(
        self,
        type: builtins.type[V] | str,
        fget: Callable[[QO], V] | None = None,
        fset: Callable[[QO, V], Any] | None = None,
        freset: Callable[[QO], Any] | None = None,
        fdel: Callable[[QO], Any] | None = None,
        doc: str | None = None,
        designable: bool = True,
        scriptable: bool = True,
        stored: bool = True,
        user: bool = False,
        constant: bool = False,
        final: bool = False,
        notify: pyqtSignal | None = None,
        revision: int = 0,
    ) -> None: ...
    def getter(self, fget: Callable[[QO], V]) -> Self:
        """Descriptor to change the getter on a property."""

    def setter(self, fset: Callable[[QO, V], Any]) -> Self:
        """Descriptor to change the setter on a property."""

    read = getter  # alias
    write = setter  # alias

    def deleter(self, fdel: Callable[[QO], Any]) -> Self:
        """Descriptor to change the deleter on a property."""

    def reset(self, freset: Callable[[QO], Any]) -> Self:
        """Descriptor to change the reset on a property."""

    def __call__(self, fget: Callable[[QO], V], *_: Any, **__: Any) -> Self:
        """Shorthand to define or update the getter function for the property."""

    @overload
    def __get__(
        self, instance: None, owner: builtins.type[QO] | None = ...
    ) -> Self: ...
    @overload
    def __get__(self, instance: QO, owner: builtins.type[QO] | None = ...) -> V: ...
    def __set__(self, instance: QObject, value: V) -> None:
        """Descriptor to set the property value."""
        ...

    def __delete__(self, instance: QObject) -> None:
        """Descriptor to delete the property value."""

    # Read-only attributes

    @property
    def type(self) -> builtins.type[V] | str:
        """Return the type of the property (read-only)."""

    @property
    def freset(self) -> Callable[[], Any] | None:
        """Return the reset function (read-only)."""
