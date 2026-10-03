import apps.blog_manager.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blog_manager", "0003_seed_defaults"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArticleImage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        upload_to=apps.blog_manager.models.article_content_image_upload_to,
                        verbose_name="Image",
                    ),
                ),
                (
                    "alt_text",
                    models.CharField(
                        blank=True,
                        help_text="Describe the image for accessibility and search engines.",
                        max_length=250,
                        verbose_name="Alt text",
                    ),
                ),
                (
                    "caption",
                    models.CharField(
                        blank=True,
                        max_length=500,
                        verbose_name="Caption",
                    ),
                ),
                ("width", models.PositiveIntegerField(default=0, editable=False, verbose_name="Width")),
                ("height", models.PositiveIntegerField(default=0, editable=False, verbose_name="Height")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Sort order")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated at")),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_images",
                        to="blog_manager.article",
                        verbose_name="Article",
                    ),
                ),
            ],
            options={
                "verbose_name": "Article image",
                "verbose_name_plural": "Article images",
                "ordering": ("sort_order", "pk"),
            },
        ),
    ]
