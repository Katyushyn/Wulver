from .base import BaseReviewProvider, Review, normalize_rating


class ManualReviewProvider(BaseReviewProvider):
    source = "manual"

    def __init__(self, reviews=None):
        self.reviews = reviews or []

    def get_reviews(self):
        normalized = []
        for index, review in enumerate(self.reviews):
            item = self._normalize_review(review, index)
            if item:
                normalized.append(item)
        return normalized

    def _normalize_review(self, review, index):
        getter = (
            review.get
            if isinstance(review, dict)
            else lambda key, default=None: getattr(review, key, default)
        )
        text = getter("text") or getter("review") or ""
        author = getter("author") or getter("organization") or "Manual review"
        organization = getter("organization") or author
        image = getter("img") or None
        logo_url = getter("logo_url") or getter("logo")

        if not logo_url and image is not None:
            logo_url = getattr(image, "url", None)

        if not text:
            return None

        return Review(
            external_id=str(getter("external_id") or f"manual-{index}"),
            source=self.source,
            author=author,
            organization=organization,
            text=text,
            rating=normalize_rating(getter("rating") or 5),
            avatar_url=getter("avatar_url"),
            logo_url=logo_url,
            url=getter("url"),
            created_at=getter("created_at") or getter("created"),
        )
