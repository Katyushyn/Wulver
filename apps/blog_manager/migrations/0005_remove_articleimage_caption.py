from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("blog_manager", "0004_articleimage"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="articleimage",
            name="caption",
        ),
    ]
