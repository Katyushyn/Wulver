import json

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from apps.blog_manager.admin import CategoryAdmin
from apps.blog_manager.models import Category
from apps.core_manager.tree_sorting import flatten_tree


class TreeSortingHelpersTest(TestCase):
    def test_flatten_tree_preserves_nested_positions(self):
        tree = [
            {"id": 2, "children": [{"id": 3, "children": []}]},
            {"id": 1, "children": []},
        ]
        self.assertEqual(
            flatten_tree(tree, {1, 2, 3}),
            [(2, None, 1), (3, 2, 1), (1, None, 2)],
        )

    def test_flatten_tree_rejects_missing_items(self):
        with self.assertRaises(ValidationError):
            flatten_tree([{"id": 1, "children": []}], {1, 2})


class TreeSortingAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_superuser(
            username="tree-admin",
            email="tree@example.com",
            password="test-password",
        )
        self.site = AdminSite()

    def post_json(self, view, payload):
        request = self.factory.post(
            "/drag-order/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.user = self.user
        return view(request)

    def test_category_changelist_renders_drag_tree(self):
        Category.objects.create(title="Blog", slug="blog")
        self.client.force_login(self.user)

        response = self.client.get("/admin/blog_manager/category/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data-tree-modal-open", response.content)
        self.assertIn(b"<dialog class=\"admin-tree-modal\"", response.content)
        self.assertIn(b"data-tree-modal-close", response.content)
        self.assertNotIn(b"column-sort_order", response.content)
        self.assertContains(response, "/admin/blog_manager/category/drag-order/")
        self.assertIn(b"/static/vendor/sortablejs/Sortable.min.", response.content)

    def test_empty_category_changelist_renders_without_tree_annotation(self):
        self.client.force_login(self.user)

        response = self.client.get("/admin/blog_manager/category/")

        self.assertEqual(response.status_code, 200)

    def test_article_changelist_hides_template_column(self):
        self.client.force_login(self.user)

        response = self.client.get("/admin/blog_manager/article/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"column-theme_template", response.content)

    def test_category_drag_order_updates_tree(self):
        first = Category.objects.create(title="First", slug="first", sort_order=1)
        second = Category.objects.create(title="Second", slug="second", sort_order=2)
        child = Category.objects.create(title="Child", slug="child", sort_order=3)
        admin = CategoryAdmin(Category, self.site)
        response = self.post_json(
            admin.drag_order_view,
            {
                "scope_id": "categories",
                "tree": [
                    {
                        "id": second.pk,
                        "children": [{"id": child.pk, "children": []}],
                    },
                    {"id": first.pk, "children": []},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual((second.parent_id, second.sort_order), (None, 1))
        self.assertEqual((child.parent_id, child.sort_order), (second.pk, 1))
        self.assertEqual((first.parent_id, first.sort_order), (None, 2))
