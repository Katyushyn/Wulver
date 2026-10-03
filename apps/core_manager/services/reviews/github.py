import logging

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

from .base import BaseReviewProvider, Review, ReviewProviderError, normalize_rating

logger = logging.getLogger(__name__)


METADATA_KEYS = {
    "rating": "rating",
    "organization": "organization",
    "logo": "logo_url",
}

# Missing metadata is treated as a normal GitHub review:
# organization falls back to the GitHub login, rating defaults to 5,
# and the logo falls back to the GitHub avatar.


def parse_review_comment(body):
    metadata = {}
    text_lines = []
    in_metadata = True

    for line in (body or "").splitlines():
        stripped = line.strip()

        if in_metadata and not stripped:
            in_metadata = False
            continue

        if in_metadata and ":" in stripped:
            key, value = stripped.split(":", 1)
            normalized_key = METADATA_KEYS.get(key.strip().lower())
            if normalized_key:
                metadata[normalized_key] = value.strip() or None
                continue

        in_metadata = False
        text_lines.append(line)

    text = "\n".join(text_lines).strip()
    if not text:
        text = (body or "").strip()

    metadata["rating"] = normalize_rating(metadata.get("rating"))
    return metadata, text


class GitHubReviewProvider(BaseReviewProvider):
    source = "github"

    def __init__(self, repository=None, issue_number=None, timeout=None, token=None):
        self.repository = repository or ""
        self.issue_number = issue_number or ""
        self.timeout = timeout or 5
        self.token = token if token is not None else settings.GITHUB_TOKEN

    @property
    def cache_key(self):
        return f"reviews:provider:{self.source}:{self.repository}:{self.issue_number}"

    def get_reviews(self):
        if not self.repository or not self.issue_number:
            return []

        url = (
            f"https://api.github.com/repos/{self.repository}"
            f"/issues/{self.issue_number}/comments"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning(
                "GitHub reviews request failed for %s issue %s: %s",
                self.repository,
                self.issue_number,
                exc.__class__.__name__,
            )
            raise ReviewProviderError("GitHub reviews request failed") from exc
        except ValueError as exc:
            logger.warning(
                "GitHub reviews response is not valid JSON for %s issue %s",
                self.repository,
                self.issue_number,
            )
            raise ReviewProviderError("GitHub reviews response is malformed") from exc

        if not isinstance(payload, list):
            logger.warning(
                "GitHub reviews response has unexpected format for %s issue %s",
                self.repository,
                self.issue_number,
            )
            raise ReviewProviderError("GitHub reviews response is malformed")

        reviews = []
        for comment in payload:
            review = self._normalize_comment(comment)
            if review:
                reviews.append(review)

        return reviews

    def _normalize_comment(self, comment):
        if not isinstance(comment, dict):
            return None

        user = comment.get("user") or {}
        author = user.get("login") or "GitHub user"
        avatar_url = user.get("avatar_url")
        metadata, text = parse_review_comment(comment.get("body") or "")
        organization = metadata.get("organization") or author
        logo_url = metadata.get("logo_url") or avatar_url
        rating = metadata.get("rating")
        if rating is None:
            rating = 5

        return Review(
            external_id=str(comment.get("id") or ""),
            source=self.source,
            author=author,
            organization=organization,
            text=text,
            rating=rating,
            avatar_url=avatar_url,
            logo_url=logo_url,
            url=comment.get("html_url"),
            created_at=parse_datetime(comment.get("created_at") or ""),
        )
