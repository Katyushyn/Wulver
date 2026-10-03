from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TemplateLayoutTests(SimpleTestCase):
    def test_root_templates_do_not_duplicate_app_templates(self):
        root_templates = Path(settings.BASE_DIR) / "templates"
        root_paths = {
            path.relative_to(root_templates).as_posix()
            for path in root_templates.rglob("*")
            if path.is_file()
        }

        duplicates = []
        apps_root = Path(settings.BASE_DIR) / "apps"
        for app_templates in apps_root.glob("*/templates"):
            for path in app_templates.rglob("*"):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(app_templates).as_posix()
                if relative_path in root_paths:
                    duplicates.append(relative_path)

        self.assertEqual(
            sorted(set(duplicates)),
            [],
            "Move module-owned templates to apps/<module>/templates and keep "
            "only global or theme templates in the root templates directory.",
        )
