import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache

from apps.core_manager.models import SiteSettings

from .github import GitHubReviewProvider
from .manual import ManualReviewProvider

logger = logging.getLogger(__name__)
OLDEST_REVIEW_DATE = datetime.min.replace(tzinfo=timezone.utc)


def get_active_providers(site_settings, manual_reviews=None):
    providers = []

    if manual_reviews:
        providers.append(ManualReviewProvider(manual_reviews))

    if site_settings.github_reviews_enabled:
        providers.append(
            GitHubReviewProvider(
                repository=site_settings.github_reviews_repository,
                issue_number=site_settings.github_reviews_issue_number,
                timeout=site_settings.github_reviews_timeout,
            )
        )

    return providers


def _provider_reviews(provider, cache_timeout):
    cached = cache.get(provider.cache_key)
    if cached is not None:
        return cached

    stale_key = f"{provider.cache_key}:stale"

    try:
        reviews = provider.get_reviews()
    except Exception as exc:
        logger.warning(
            "Review provider %s failed: %s",
            provider.source,
            exc.__class__.__name__,
        )
        return cache.get(stale_key, [])

    result = [review.to_dict() for review in reviews]
    cache.set(provider.cache_key, result, cache_timeout)
    cache.set(stale_key, result, None)
    return result


def get_reviews(limit=None, manual_reviews=None):
    site_settings = SiteSettings.get_solo()

    if not site_settings.reviews_enabled:
        return []

    limit = site_settings.reviews_limit if limit is None else limit
    limit = max(int(limit or 0), 0)
    if limit == 0:
        return []

    providers = get_active_providers(site_settings, manual_reviews)
    if not providers:
        return []

    combined_cache_key = "reviews:combined:{}:{}".format(
        ",".join(provider.cache_key for provider in providers),
        limit,
    )
    cached = cache.get(combined_cache_key)
    if cached is not None:
        return cached

    reviews = []
    seen = set()
    for provider in providers:
        for review in _provider_reviews(
            provider,
            site_settings.reviews_cache_timeout,
        ):
            unique_key = (
                review.get("source"),
                review.get("external_id"),
            )
            if unique_key in seen:
                continue
            seen.add(unique_key)
            reviews.append(review)

    reviews.sort(
        key=lambda review: review.get("created_at") or OLDEST_REVIEW_DATE,
        reverse=True,
    )
    reviews = reviews[:limit]
    cache.set(combined_cache_key, reviews, site_settings.reviews_cache_timeout)
    return reviews


class YouTubeReviewProviderPlaceholder:
    """Future provider placeholder; real implementation needs YouTube API credentials."""

    pass
