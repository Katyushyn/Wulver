from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from apps.core_manager.models import SiteSettings
from .base import Review, ReviewProviderError
from .github import GitHubReviewProvider, parse_review_comment
from .service import get_reviews


class ReviewMetadataParserTests(SimpleTestCase):
    def test_parses_optional_metadata_block(self):
        metadata, text = parse_review_comment(
            "rating: 6\n"
            "organization: Example Organization\n"
            "logo: https://example.com/logo.png\n"
            "\n"
            "Very professional work."
        )

        self.assertEqual(metadata["rating"], 5)
        self.assertEqual(metadata["organization"], "Example Organization")
        self.assertEqual(metadata["logo_url"], "https://example.com/logo.png")
        self.assertEqual(text, "Very professional work.")

    def test_plain_comment_stays_as_review_text(self):
        metadata, text = parse_review_comment("Just a useful review.")

        self.assertIsNone(metadata["rating"])
        self.assertEqual(text, "Just a useful review.")


@override_settings(GITHUB_TOKEN="secret-token")
class GitHubReviewProviderTests(SimpleTestCase):
    @patch("apps.core_manager.services.reviews.github.requests.get")
    def test_normalizes_github_issue_comments(self, mocked_get):
        response = Mock()
        response.json.return_value = [
            {
                "id": 42,
                "body": "rating: 4\norganization: Client\n\nGreat result.",
                "html_url": "https://github.com/repo/issues/1#issuecomment-42",
                "created_at": "2026-08-08T10:00:00Z",
                "user": {
                    "login": "alice",
                    "avatar_url": "https://example.com/avatar.png",
                },
            }
        ]
        mocked_get.return_value = response

        reviews = GitHubReviewProvider(
            repository="example/wulver-reviews",
            issue_number=123,
            timeout=5,
        ).get_reviews()

        self.assertEqual(reviews[0].external_id, "42")
        self.assertEqual(reviews[0].organization, "Client")
        self.assertEqual(reviews[0].rating, 4)
        self.assertEqual(reviews[0].text, "Great result.")
        self.assertEqual(
            mocked_get.call_args.kwargs["headers"]["Authorization"],
            "Bearer secret-token",
        )


class ReviewServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        site_settings = SiteSettings.get_solo()
        site_settings.reviews_enabled = True
        site_settings.reviews_limit = 3
        site_settings.reviews_cache_timeout = 1800
        site_settings.github_reviews_enabled = True
        site_settings.save(
            update_fields=[
                "reviews_enabled",
                "reviews_limit",
                "reviews_cache_timeout",
                "github_reviews_enabled",
            ]
        )

    @patch("apps.core_manager.services.reviews.service.get_active_providers")
    def test_uses_stale_provider_cache_when_provider_fails(self, mocked_providers):
        provider = Mock()
        provider.source = "github"
        provider.cache_key = "reviews:provider:github:test"
        provider.get_reviews.return_value = [
            Review(
                external_id="1",
                source="github",
                author="alice",
                organization="Client",
                text="Cached review",
                rating=5,
                avatar_url=None,
                logo_url=None,
                url=None,
                created_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
            )
        ]
        mocked_providers.return_value = [provider]

        self.assertEqual(get_reviews()[0]["text"], "Cached review")
        cache.delete("reviews:provider:github:test")
        cache.delete("reviews:combined:reviews:provider:github:test:3")
        provider.get_reviews.side_effect = ReviewProviderError("down")

        with self.assertLogs(
            "apps.core_manager.services.reviews.service",
            level="WARNING",
        ):
            self.assertEqual(get_reviews()[0]["text"], "Cached review")
