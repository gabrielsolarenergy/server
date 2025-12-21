import boto3
from botocore.client import Config
from PIL import Image
import io
import uuid
import os
from fastapi import UploadFile

# Acestea ar trebui să stea în .env pe Railway
RAILWAY_STORAGE_ENDPOINT = os.getenv("RAILWAY_STORAGE_ENDPOINT", "https://storage.railway.app")
RAILWAY_STORAGE_BUCKET = os.getenv("RAILWAY_STORAGE_BUCKET")
RAILWAY_STORAGE_ACCESS_KEY = os.getenv("RAILWAY_STORAGE_ACCESS_KEY")
RAILWAY_STORAGE_SECRET_KEY = os.getenv("RAILWAY_STORAGE_SECRET_KEY")

# Configurare client S3-compatible pentru Railway
s3_client = boto3.client(
    's3',
    endpoint_url=RAILWAY_STORAGE_ENDPOINT,
    aws_access_key_id=RAILWAY_STORAGE_ACCESS_KEY,
    aws_secret_access_key=RAILWAY_STORAGE_SECRET_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

async def upload_image_to_bucket(file: UploadFile) -> str:
    """
    Procesează imaginea (redimensionare + WebP) și o urcă în bucket.
    Returnează URL-ul public al imaginii.
    """
    try:
        # 1. Citim fișierul în memorie
        content = await file.read()
        image = Image.open(io.BytesIO(content))

        # 2. Conversie la RGB dacă e PNG/RGBA (necesar pentru WebP/JPEG)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # 3. Redimensionare inteligentă (max 1024px pe orice latură)
        max_size = 1024
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # 4. Salvare în buffer ca WebP (compresie excelentă)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='WEBP', quality=80)
        img_byte_arr.seek(0)

        # 5. Generare nume unic
        file_extension = "webp"
        file_name = f"requests/{uuid.uuid4()}.{file_extension}"

        # 6. Upload efectiv
        s3_client.upload_fileobj(
            img_byte_arr,
            RAILWAY_STORAGE_BUCKET,
            file_name,
            ExtraArgs={
                'ContentType': 'image/webp'
            }
        )

        # 7. Construim URL-ul (Railway folosește de obicei acest format)
        # Atenție: verifică dacă bucket-ul tău este public în setările Railway Storage
        return f"{RAILWAY_STORAGE_ENDPOINT}/{RAILWAY_STORAGE_BUCKET}/{file_name}"

    except Exception as e:
        print(f"Eroare la procesare/upload imagine: {e}")
        raise e