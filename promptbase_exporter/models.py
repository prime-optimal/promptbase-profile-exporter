from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Profile:
    username: str
    uid: str


@dataclass(frozen=True)
class PromptRecord:
    title: str
    description: str
    slug: str
    prompt_type: str
    domain: str
    created: int
    price: float
    discount: float = 0.0
    views: int = 0
    sales: int = 0
    downloads: int = 0
    favorites: int = 0
    rating: float = 0.0
    reviews: int = 0

    @property
    def url(self) -> str:
        return f"https://promptbase.com/prompt/{self.slug}"

    @property
    def created_iso(self) -> str:
        if not self.created:
            return ""
        return datetime.fromtimestamp(self.created / 1000, tz=timezone.utc).isoformat()

    @property
    def is_text(self) -> bool:
        return self.domain == "text"

    @property
    def is_image(self) -> bool:
        return self.domain == "image"

    @property
    def is_free(self) -> bool:
        return self.price == 0
