from datetime import timedelta
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from django_comments.models import Comment
from apps.blog_manager.models import Article, Category
from .models import LatestCommentsModule
from .templatetags.comment_modules import latest_comments_module


class LatestCommentsModuleTests(TestCase):
    def test_limits_visibility_descendants_and_excerpt(self):
        root = Category.objects.create(title="Root", slug="root")
        child = Category.objects.create(title="Child", slug="child", parent=root)
        module = LatestCommentsModule.objects.create(name="Test", slug="test", comments_count=5, excerpt_words=3)
        module.categories.add(root)
        now = timezone.now()
        for n in range(7):
            article = Article.objects.create(
                title=f"Article {n}", slug=f"article-{n}", category=child,
                publish=now-timedelta(days=1), is_published=n!=6,
            )
            for j in range(2):
                Comment.objects.create(
                    content_type=ContentType.objects.get_for_model(Article),
                    object_pk=str(article.pk), site_id=settings.SITE_ID,
                    comment="<b>one two three four five</b>", user_name="Reader",
                    submit_date=now-timedelta(minutes=n*2+j), is_public=True,
                )
        rows = latest_comments_module("test")
        self.assertEqual(len(rows), 5)
        self.assertEqual(len({r["article"].pk for r in rows}), 5)
        self.assertTrue(all(len(r["excerpt"].split()) <= 3 for r in rows))
        self.assertTrue(all("<b>" not in r["excerpt"] for r in rows))
        self.assertTrue(all(r["article"].is_published for r in rows))
        Comment.objects.all().update(is_public=False)
        self.assertEqual(latest_comments_module("test"), [])
        Comment.objects.all().update(is_public=True, is_removed=True)
        self.assertEqual(latest_comments_module("test"), [])
        Comment.objects.all().update(is_removed=False)
        module.include_descendants = False
        module.save()
        self.assertEqual(latest_comments_module("test"), [])
        module.include_descendants = True
        module.per_article_limit = 2
        module.save()
        rows = latest_comments_module("test")
        self.assertEqual(rows[0]["article"], rows[1]["article"])
        module.is_active = False
        module.save()
        self.assertEqual(latest_comments_module("test"), [])
        self.assertEqual(latest_comments_module("missing"), [])
