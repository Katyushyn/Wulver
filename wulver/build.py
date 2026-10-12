"""Bundle system resources, never a site's database, media or configuration."""
from pathlib import Path
import shutil
import os

from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent.parent
        target = Path(self.build_lib) / 'wulver' / 'resources'
        demo_target = target / 'demo' / 'story.zip'
        # Prevent a prior private build from leaking into a subsequent clean wheel.
        if demo_target.exists():
            demo_target.unlink()
        private_demo = os.environ.get('WULVER_PRIVATE_DEMO')
        if private_demo:
            demo_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(private_demo, demo_target)
        for folder in ('static', 'locale'):
            shutil.copytree(root / folder, target / folder, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('themes', '.DS_Store', '__pycache__'))
        (target / 'templates').mkdir(parents=True, exist_ok=True)
        for name in ('sitemap.xml', 'sitemap_index.xml', 'sitemap.xsl'):
            shutil.copy2(root / 'templates' / name, target / 'templates' / name)
        (target / 'project').mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / '.env.example', target / 'project' / 'env.example')
        source = (root / 'config' / 'settings.py').read_text()
        source = source.replace('BASE_DIR = Path(__file__).resolve().parent.parent',
            'BASE_DIR = Path(__file__).resolve().parent.parent\n'
            'from wulver.paths import APPS_DIR, RESOURCES_DIR')
        source = source.replace('BASE_DIR / "apps"', 'APPS_DIR')
        source = source.replace('BASE_DIR / "templates",',
            'BASE_DIR / "templates",\n            RESOURCES_DIR / "templates",')
        source = source.replace('BASE_DIR / "locale",',
            'BASE_DIR / "locale",\n    RESOURCES_DIR / "locale",')
        source = source.replace('BASE_DIR / "static",',
            'BASE_DIR / "static",\n    RESOURCES_DIR / "static",')
        (target / 'project' / 'settings.py').write_text(source)
        for name in ('urls.py', 'wsgi.py', 'asgi.py'):
            if name == 'urls.py':
                urls = (root / 'config' / name).read_text().replace(
                    'prefix_default_language=False',
                    'prefix_default_language=getattr(settings, "PREFIX_DEFAULT_LANGUAGE", False)')
                (target / 'project' / name).write_text(urls)
            else:
                shutil.copy2(root / 'config' / name, target / 'project' / name)
