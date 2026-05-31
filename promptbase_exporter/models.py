from __future__ import annotations

from dataclasses import dataclass


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

    @property
    def url(self) -> str:
        return f"https://promptbase.com/prompt/{self.slug}"

    @property
    def is_text(self) -> bool:
        return self.domain == "text"

    @property
    def is_image(self) -> bool:
        return self.domain == "image"
