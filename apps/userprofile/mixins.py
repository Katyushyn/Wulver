import io
from pathlib import PurePosixPath

import pillow_avif  # noqa: F401
from PIL import Image, ImageOps
from django.core.files.base import ContentFile


class AvatarProcessingMixin:
    def process_avatar(
        self,
        avatar_field_name="avatar",
        size=(150, 150),
        previous_name="",
    ):
        avatar_field = getattr(self, avatar_field_name)
        if not avatar_field or not avatar_field.name:
            return False

        storage = avatar_field.storage
        source_name = avatar_field.name

        try:
            with storage.open(source_name, "rb") as source_file:
                with Image.open(source_file) as image:
                    image.load()
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    avatar = ImageOps.fit(
                        image,
                        size,
                        method=Image.Resampling.LANCZOS,
                        centering=(0.5, 0.5),
                    )
                    output = io.BytesIO()
                    avatar.save(
                        output,
                        format="AVIF",
                        quality=85,
                        speed=6,
                    )
        except Exception:
            return False

        source_path = PurePosixPath(source_name)
        target_name = str(
            source_path.with_name(f"{source_path.stem}.avif")
        )
        if target_name == source_name:
            target_name = str(
                source_path.with_name(f"{source_path.stem}-processed.avif")
            )

        saved_name = storage.save(target_name, ContentFile(output.getvalue()))
        avatar_field.name = saved_name

        for obsolete_name in {source_name, previous_name}:
            if (
                obsolete_name
                and obsolete_name != saved_name
                and storage.exists(obsolete_name)
            ):
                storage.delete(obsolete_name)

        return True
