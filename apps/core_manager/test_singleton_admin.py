from django.contrib import admin
from django.test import SimpleTestCase

from apps.ai_assistant.models import AssistantProfile
from apps.backup_manager.models import BackupSettings
from apps.blog_manager.models import BlogSettings
from apps.comments_manager.models import CommentSettings
from apps.core_manager.admin_mixins import SingletonAdminMixin
from apps.core_manager.models import SiteSettings
from apps.userprofile.models import PersonalAccountTemplate


class _ParentAdmin:
    def render_change_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url="",
        obj=None,
    ):
        return context


class _TestSingletonAdmin(SingletonAdminMixin, _ParentAdmin):
    pass


class SingletonAdminMixinTests(SimpleTestCase):
    def test_hides_save_and_continue_without_changing_other_context(self):
        context = _TestSingletonAdmin().render_change_form(
            request=None,
            context={"show_save": True, "custom": "value"},
            change=True,
        )

        self.assertFalse(context["show_save_and_continue"])
        self.assertTrue(context["show_save"])
        self.assertEqual(context["custom"], "value")

    def test_mixin_is_limited_to_effectively_singleton_admin_models(self):
        singleton_models = (
            AssistantProfile,
            BackupSettings,
            BlogSettings,
            CommentSettings,
            PersonalAccountTemplate,
            SiteSettings,
        )

        for model in singleton_models:
            with self.subTest(model=model._meta.label):
                self.assertIsInstance(
                    admin.site._registry[model],
                    SingletonAdminMixin,
                )
