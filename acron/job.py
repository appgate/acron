from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

__all__ = [
    "Job",
]


@dataclass(frozen=True)
class Job:
    schedule: str
    func: Callable[[], Awaitable[None]]
    name: Optional[str] = None
    enabled: bool = True
