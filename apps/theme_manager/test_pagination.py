from django.core.paginator import Paginator
from django.test import SimpleTestCase

from apps.theme_manager.templatetags.pagination import elided_page_range


class ElidedPageRangeTagTests(SimpleTestCase):
    def test_returns_empty_tuple_without_page_object(self):
        self.assertEqual(elided_page_range(None), ())

    def test_returns_default_elided_page_range(self):
        page_obj = Paginator(range(200), 10).page(10)

        self.assertEqual(
            list(elided_page_range(page_obj)),
            [1, "…", 8, 9, 10, 11, 12, "…", 20],
        )

    def test_accepts_custom_range_sizes(self):
        page_obj = Paginator(range(200), 10).page(10)

        self.assertEqual(
            list(elided_page_range(page_obj, on_each_side=1, on_ends=2)),
            [1, 2, "…", 9, 10, 11, "…", 19, 20],
        )
