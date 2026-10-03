from types import SimpleNamespace

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.template.loader import get_template
from django.test import RequestFactory, TestCase
from django_comments.models import Comment
from django.urls import reverse

from .defaults import (
    DEFAULT_COMMENT_STYLESHEET,
    DEFAULT_COMMENT_TEMPLATES,
    DEFAULT_COMMENT_TEXTS,
)
from .models import CommentSettings, CommentTemplate
from .signals import enforce_comment_posting_policy


class CommentAppearanceTests(TestCase):
    def test_comment_templates_are_seeded(self):
        self.assertEqual(CommentTemplate.objects.count(), 3)
        self.assertEqual(
            set(CommentTemplate.objects.values_list("template_type", flat=True)),
            set(DEFAULT_COMMENT_TEMPLATES),
        )

    def test_comment_templates_compile_and_stylesheet_is_served(self):
        for template_name in ("comments/form.html", "comments/list.html", "comments/comment.html"):
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))

        response = self.client.get(reverse("comments_stylesheet"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/css; charset=utf-8")
        self.assertContains(response, ".comment-card")

    def test_admin_reset_restores_all_comment_texts_and_styles(self):
        admin_user = User.objects.create_superuser(
            username="comment-admin",
            email="comment-admin@example.com",
            password="password",
        )
        settings = CommentSettings.get_solo()
        settings.form_title_en = "Broken"
        settings.form_title_uk = "Зламано"
        settings.stylesheet = ".broken {}"
        settings.save()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("admin:comments_manager_commentsettings_reset_defaults", args=[settings.pk])
        )

        self.assertEqual(response.status_code, 302)
        settings.refresh_from_db()
        self.assertEqual(settings.form_title_en, DEFAULT_COMMENT_TEXTS["en"]["form_title"])
        self.assertEqual(settings.form_title_uk, DEFAULT_COMMENT_TEXTS["uk"]["form_title"])
        self.assertEqual(settings.stylesheet, DEFAULT_COMMENT_STYLESHEET)

    def test_admin_can_reset_one_comment_template(self):
        admin_user = User.objects.create_superuser(
            username="template-admin",
            email="template-admin@example.com",
            password="password",
        )
        comment_template = CommentTemplate.objects.get(template_type="form")
        comment_template.code = "broken"
        comment_template.save()
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("admin:comments_manager_commenttemplate_reset_defaults", args=[comment_template.pk])
        )

        self.assertEqual(response.status_code, 302)
        comment_template.refresh_from_db()
        self.assertEqual(comment_template.code, DEFAULT_COMMENT_TEMPLATES["form"])


class CommentPostingPolicyTests(TestCase):
    def setUp(self):
        self.settings = CommentSettings.get_solo()
        self.user = User.objects.create_user("commenter", password="password")
        self.request = RequestFactory().post("/comments/post/")
        self.request.user = self.user

    def candidate(self, ip_address="127.0.0.1"):
        return SimpleNamespace(ip_address=ip_address, is_public=True)

    def create_comment(self, user=None, ip_address="127.0.0.1"):
        return Comment.objects.create(
            content_type=ContentType.objects.get_for_model(User),
            object_pk=str(self.user.pk),
            site=Site.objects.get_current(),
            user=user,
            user_name=(user.username if user else "Guest"),
            user_email="commenter@example.com",
            comment="Test comment",
            ip_address=ip_address,
        )

    def test_anonymous_comments_are_forbidden_by_default(self):
        self.request.user = SimpleNamespace(is_authenticated=False)

        allowed = enforce_comment_posting_policy(
            Comment, self.candidate(), self.request
        )

        self.assertFalse(allowed)

    def test_default_limit_is_three_comments_per_ten_minutes(self):
        self.assertEqual(self.settings.rate_limit_count, 3)
        self.assertEqual(self.settings.rate_limit_window_minutes, 10)
        for _ in range(3):
            self.create_comment(user=self.user)

        allowed = enforce_comment_posting_policy(
            Comment, self.candidate(), self.request
        )

        self.assertFalse(allowed)

    def test_limit_also_applies_by_ip_address(self):
        for index in range(3):
            other_user = User.objects.create_user(f"other-{index}")
            self.create_comment(user=other_user)

        allowed = enforce_comment_posting_policy(
            Comment, self.candidate(), self.request
        )

        self.assertFalse(allowed)

    def test_moderation_mode_hides_new_comment(self):
        self.settings.publication_mode = CommentSettings.PublicationMode.MODERATION
        self.settings.save()
        candidate = self.candidate()

        allowed = enforce_comment_posting_policy(Comment, candidate, self.request)

        self.assertTrue(allowed)
        self.assertFalse(candidate.is_public)
