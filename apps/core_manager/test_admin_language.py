from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core_manager.templatetags.admin_language import (
    admin_language_links,
    has_admin_actions,
)


@override_settings(
    LANGUAGE_CODE="en",
    LANGUAGES=(("en", "English"), ("uk", "Ukrainian")),
)
class AdminLanguageLinksTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def links_for(self, path, language):
        request = self.factory.get(path)
        request.LANGUAGE_CODE = language
        return {
            item["code"]: item
            for item in admin_language_links({"request": request})
        }

    def test_adds_non_default_language_prefix(self):
        links = self.links_for("/admin/blog_manager/article/31/change/", "en")

        self.assertEqual(
            links["uk"]["url"],
            "/uk/admin/blog_manager/article/31/change/",
        )
        self.assertTrue(links["en"]["is_active"])

    def test_removes_non_default_language_prefix_for_default_language(self):
        links = self.links_for(
            "/uk/admin/blog_manager/article/31/change/",
            "uk",
        )

        self.assertEqual(
            links["en"]["url"],
            "/admin/blog_manager/article/31/change/",
        )
        self.assertTrue(links["uk"]["is_active"])

    def test_replaces_existing_prefix_and_preserves_query_string(self):
        links = self.links_for("/uk/admin/?page=2&filter=a&filter=b", "uk")

        self.assertEqual(links["en"]["url"], "/admin/?page=2&filter=a&filter=b")
        self.assertEqual(links["uk"]["url"], "/uk/admin/?page=2&filter=a&filter=b")

    def test_does_not_strip_a_partial_language_segment(self):
        links = self.links_for("/ukulele/admin/", "en")

        self.assertEqual(links["en"]["url"], "/ukulele/admin/")
        self.assertEqual(links["uk"]["url"], "/uk/ukulele/admin/")

    def test_whitespace_only_unfold_action_block_is_empty(self):
        self.assertFalse(has_admin_actions(" \n\t "))
        self.assertTrue(has_admin_actions('<div class="action">Info</div>'))
