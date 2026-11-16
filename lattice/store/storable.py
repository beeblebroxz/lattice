"""Store-awareness for dag.Model objects.

``Store`` records where an object lives by setting ``_store_ref`` and
``_store_path`` on it. ``Storable`` is the mixin that turns those attributes
into the object-level API: ``obj.path()``, ``obj.save()`` and ``obj.store``.

dag.Model used to carry these methods itself; dag has no store of its own, so
they live here, next to the Store that drives them.
"""

import weakref
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .core import Store


class Storable:
    """Mixin giving a dag.Model access to the Store it is kept in.

    List it before dag.Model in the bases::

        class MyModel(Storable, dag.Model):
            ...

    Lattice's instruments and trading models (Book, Trade, Position) already
    include it. A plain dag.Model can still be stored and saved with
    ``db[path] = obj`` / ``db.save(obj)``; it just lacks these methods.
    """

    # Set by Store when the object is stored or loaded, cleared on delete.
    _store_ref: Optional["weakref.ReferenceType[Store]"] = None
    _store_path: Optional[str] = None

    def path(self) -> Optional[str]:
        """Return this object's path in its store, or None if it is not stored.

        Example:
            option = db["/Instruments/AAPL_C_150"]
            print(option.path())  # "/Instruments/AAPL_C_150"
        """
        return self._store_path

    @property
    def store(self) -> "Store":
        """The Store this object belongs to.

        Raises:
            RuntimeError: If the object is not associated with a store, or the
                store has been garbage collected.

        Example:
            option = db["/Instruments/AAPL_C_150"]
            other = option.store["/Instruments/GOOGL_C_100"]
        """
        if self._store_ref is None:
            raise RuntimeError("Object is not associated with a store.")
        store = self._store_ref()
        if store is None:
            raise RuntimeError("Store has been garbage collected.")
        return store

    def save(self) -> None:
        """Persist this object at its path in its store.

        Raises:
            RuntimeError: If the object is not associated with a store. Use
                ``db[path] = obj`` to store it first.

        Example:
            option = db["/Instruments/AAPL_C_150"]
            option.Strike.set(160.0)
            option.save()
        """
        if self._store_ref is None or self._store_path is None:
            raise RuntimeError(
                "Object is not associated with a store. "
                "Use db[path] = obj to store it first."
            )
        self.store[self._store_path] = self
