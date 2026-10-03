from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Review:
    external_id: str
    source: str
    author: str
    organization: str | None
    text: str
    rating: int | None
    avatar_url: str | None
    logo_url: str | None
    url: str | None
    created_at: datetime | None

    @property
    def display_name(self):
        return self.organization or self.author

    @property
    def stars(self):
        if self.rating is None:
            return ""
        return "★" * self.rating

    def to_dict(self):
        return {
            "external_id": self.external_id,
            "source": self.source,
            "author": self.author,
            "organization": self.organization,
            "display_name": self.display_name,
            "text": self.text,
            "rating": self.rating,
            "stars": self.stars,
            "avatar_url": self.avatar_url,
            "logo_url": self.logo_url,
            "url": self.url,
            "created_at": self.created_at,
        }


class ReviewProviderError(Exception):
    pass


class BaseReviewProvider(ABC):
    source = "base"

    @property
    def cache_key(self):
        return f"reviews:provider:{self.source}"

    @abstractmethod
    def get_reviews(self):
        raise NotImplementedError


def normalize_rating(value):
    if value in ("", None):
        return None

    try:
        rating = int(value)
    except (TypeError, ValueError):
        return None

    return max(1, min(rating, 5))
