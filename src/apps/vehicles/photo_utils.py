"""
Vehicle photo processing helpers.
"""
import io
import os

from django.core.files.uploadedfile import InMemoryUploadedFile

from PIL import Image, ImageOps

# Photos larger than either bound are recompressed before saving.
MAX_DIMENSION = 1920          # px, longest edge
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB
JPEG_QUALITY = 85


def compress_uploaded_photo(uploaded_file):
    """
    Downscale/re-encode an oversized uploaded image while keeping good
    visual quality. Small images pass through untouched. Returns the file
    to save (original or a compressed replacement).
    """
    try:
        needs_resize = False
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()

        if max(image.size) > MAX_DIMENSION:
            needs_resize = True
        size = getattr(uploaded_file, 'size', 0) or 0
        if size > MAX_UPLOAD_BYTES:
            needs_resize = True
        if not needs_resize:
            uploaded_file.seek(0)
            return uploaded_file

        # Respect EXIF orientation, drop alpha for JPEG output.
        image = ImageOps.exif_transpose(image)
        if max(image.size) > MAX_DIMENSION:
            image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        buffer.seek(0)

        base = os.path.splitext(os.path.basename(uploaded_file.name))[0]
        return InMemoryUploadedFile(
            buffer, 'ImageField', f'{base}.jpg', 'image/jpeg',
            buffer.getbuffer().nbytes, None,
        )
    except Exception:
        # Never block an upload because compression failed.
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return uploaded_file
