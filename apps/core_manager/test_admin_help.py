from html import escape

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core_manager.admin_help import (
    ADMIN_HELP,
    HELP_CHANGE_FORM_TEMPLATE,
    HELP_CHANGE_LIST_TEMPLATE,
)


class AdminHelpTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin-help-test",
            email="admin-help@example.com",
            password="test",
        )
        self.client.force_login(self.user)

    def test_every_sidebar_model_has_registered_detailed_help(self):
        self.assertEqual(len(ADMIN_HELP), 37)

        for label, guide in ADMIN_HELP.items():
            with self.subTest(label=label):
                model = apps.get_model(label)
                self.assertIn(model, admin.site._registry)
                self.assertTrue(guide["title"])
                self.assertTrue(guide["summary"])
                self.assertGreaterEqual(len(guide["sections"]), 3)
                for section in guide["sections"]:
                    self.assertTrue(section["title"])
                    self.assertTrue(section.get("items") or section.get("paragraphs"))

    def test_generic_help_templates_are_attached_without_losing_custom_ones(self):
        custom_list_labels = {
            "ai_assistant.knowledgechunk",
            "backup_manager.backupsnapshot",
            "blog_manager.category",
            "theme_manager.theme",
        }
        custom_form_labels = {
            "comments_manager.commentsettings",
            "comments_manager.commenttemplate",
            "core_manager.sitemapsettings",
            "core_manager.sitesettings",
            "userprofile.authenticationemailtemplate",
            "userprofile.authenticationtemplate",
            "userprofile.personalaccounttemplate",
        }

        for label in ADMIN_HELP:
            model_admin = admin.site._registry[apps.get_model(label)]
            with self.subTest(label=label):
                if label not in custom_list_labels:
                    self.assertEqual(
                        model_admin.change_list_template,
                        HELP_CHANGE_LIST_TEMPLATE,
                    )
                if label not in custom_form_labels:
                    self.assertEqual(
                        model_admin.change_form_template,
                        HELP_CHANGE_FORM_TEMPLATE,
                    )

    def test_every_menu_changelist_renders_its_own_info_dialog(self):
        for label, guide in ADMIN_HELP.items():
            app_label, model_name = label.split(".", 1)
            url = reverse(f"admin:{app_label}_{model_name}_changelist")

            with self.subTest(label=label):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-admin-help-open")
                self.assertContains(response, "data-admin-help-dialog")
                self.assertContains(response, "admin-action-group")
                self.assertContains(response, guide["title"])
                self.assertContains(response, escape(guide["summary"]))
