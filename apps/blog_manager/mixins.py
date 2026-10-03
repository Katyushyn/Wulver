import os
from PIL import Image, ImageOps
import pillow_avif
from django.conf import settings


def _media_rel_path(path):
    return os.path.relpath(path, settings.MEDIA_ROOT).replace(os.sep, "/")


class ImageProcessingMixin:
    def handle_content_image(
        self,
        image_field_name,
        max_width=1200,
        quality=85,
    ):
        image_field = getattr(self, image_field_name)
        if not image_field:
            return None

        image_path = image_field.path
        image_basename, _extension = os.path.splitext(image_field.name)
        avif_image_path = os.path.join(
            settings.MEDIA_ROOT,
            f"{image_basename}.avif",
        )

        with Image.open(image_path) as source_image:
            image = ImageOps.exif_transpose(source_image).copy()

        if image.width > max_width:
            new_height = round((max_width / image.width) * image.height)
            image = image.resize(
                (max_width, new_height),
                Image.Resampling.LANCZOS,
            )

        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            image = image.convert("RGBA")
        else:
            image = image.convert("RGB")

        image.save(avif_image_path, format="AVIF", quality=quality)

        if os.path.abspath(image_path) != os.path.abspath(avif_image_path):
            os.remove(image_path)

        setattr(
            self,
            image_field_name,
            _media_rel_path(avif_image_path),
        )
        return image.size

    def handle_images(
        self,
        image_field_name,
        crop_field_name,
        mob_crop_field_name,
        max_width=1200,
        crop_size=(600, 400),
        mob_crop_size=(380, 253)
    ):
        image_field = getattr(self, image_field_name)
        crop_field = getattr(self, crop_field_name)
        mob_crop_field = getattr(self, mob_crop_field_name)

        crop_path = os.path.join(settings.MEDIA_ROOT, crop_field.name) if crop_field else None
        mob_crop_path = os.path.join(settings.MEDIA_ROOT, mob_crop_field.name) if mob_crop_field else None

        if not image_field:
            # Якщо зображення очищене — видаляємо кропи
            if crop_path and os.path.exists(crop_path):
                os.remove(crop_path)
            if mob_crop_path and os.path.exists(mob_crop_path):
                os.remove(mob_crop_path)

            setattr(self, crop_field_name, '')
            setattr(self, mob_crop_field_name, '')
            return

        # Основне зображення
        image_path = image_field.path
        image_basename, _ = os.path.splitext(image_field.name)

        with Image.open(image_path) as source_image:
            img = source_image.copy()
        width, height = img.size

        # Масштабуємо, якщо перевищує max_width
        if width > max_width:
            new_height = int((max_width / width) * height)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Функція для створення кропа
        def make_crop(img, crop_size):
            crop_width, crop_height = crop_size
            img_resized = img.copy()

            if img_resized.width > crop_width:
                new_height = int((crop_width / img_resized.width) * img_resized.height)
                img_resized = img_resized.resize((crop_width, new_height), Image.LANCZOS)

            if img_resized.height < crop_height:
                new_width = int((crop_height / img_resized.height) * img_resized.width)
                img_resized = img_resized.resize((new_width, crop_height), Image.LANCZOS)

            left = (img_resized.width - crop_width) // 2
            top = (img_resized.height - crop_height) // 2
            return img_resized.crop((left, top, left + crop_width, top + crop_height))

        # Кроп для десктопу
        img_cropped = make_crop(img, crop_size)
        # Кроп для мобільного
        img_cropped_mob = make_crop(img, mob_crop_size)

        # Шляхи для збереження .avif
        avif_image_path = os.path.join(settings.MEDIA_ROOT, f"{image_basename}.avif")
        avif_crop_path = os.path.join(settings.MEDIA_ROOT, f"{image_basename}_crop.avif")
        avif_crop_mob_path = os.path.join(settings.MEDIA_ROOT, f"{image_basename}_crop_mob.avif")

        # Зберігаємо в AVIF
        img.save(avif_image_path, format='AVIF', quality=85)
        img_cropped.save(avif_crop_path, format='AVIF', quality=60)
        img_cropped_mob.save(avif_crop_mob_path, format='AVIF', quality=60)

        # The initially uploaded JPEG/PNG/WebP is only a processing source.
        # Keep the generated AVIF when the upload itself was already an AVIF.
        if os.path.abspath(image_path) != os.path.abspath(avif_image_path):
            os.remove(image_path)

        # Встановлюємо шляхи у відповідні поля
        image_rel = _media_rel_path(avif_image_path)
        crop_rel = _media_rel_path(avif_crop_path)
        crop_mob_rel = _media_rel_path(avif_crop_mob_path)

        setattr(self, image_field_name, image_rel)
        setattr(self, crop_field_name, crop_rel)
        setattr(self, mob_crop_field_name, crop_mob_rel)


class MemProcessingMixin:
    """Compatibility base retained for historical blog migrations."""

    pass
