from __future__ import annotations
from abc import ABC, abstractmethod
from threading import RLock
from typing import Dict, Generic, TypeVar, Optional, List

K = TypeVar("K")
T = TypeVar("T")

class BaseCsvCache(ABC, Generic[K, T]):
    """
    Generic CSV-backed in-memory cache.

    Subclasses define:
      - how to load rows from CSV into objects
      - how to write an object back to a CSV row
      - how to extract the key from an object
    """

    def __init__(self, csv_path: str):
        self._csv_path = csv_path
        self._lock = RLock()
        self._loaded = False
        self._data: Dict[K, T] = {}

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._load_from_csv(self._csv_path)
            self._loaded = True

    def get(self, key: K) -> Optional[T]:
        self.load()
        with self._lock:
            return self._data.get(key)

    def all(self) -> List[T]:
        self.load()
        with self._lock:
            return list(self._data.values())

    def upsert(self, value: T) -> None:
        self.load()
        key = self.key_of(value)
        with self._lock:
            self._data[key] = value

    def remove(self, key: K) -> bool:
        self.load()
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._loaded = False

    def size(self) -> int:
        self.load()
        with self._lock:
            return len(self._data)

    # ---- Required per-cache behavior ----

    @abstractmethod
    def key_of(self, value: T) -> K:
        """Return the key used to store this object."""
        raise NotImplementedError

    @abstractmethod
    def _load_from_csv(self, csv_path: str) -> None:
        """Populate self._data from the CSV."""
        raise NotImplementedError

    @abstractmethod
    def append_to_csv(self, value: T) -> None:
        """Persist one new object to the CSV (append-only)."""
        raise NotImplementedError
    
    def save(self, value: T) -> None:
        self.upsert(value)
        self.append_to_csv(value)
    
