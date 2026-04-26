from io import BytesIO

from PIL import Image


def compress_image(file_obj, quality: int = 70):
    """
    Compress an image into an in-memory JPEG buffer before upload.
    """
    img = Image.open(file_obj)
    img = img.convert("RGB")
    buffer = BytesIO()
    img.save(buffer, format="JPEG", optimize=True, quality=quality)
    buffer.seek(0)
    return buffer
