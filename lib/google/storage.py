from os.path import join
from django.conf import settings
from google.cloud import storage


GCLOUD_PATH = join(settings.BASE_DIR, settings.GS_CREDENTIAL_PATH)
__gcloud_client = storage.Client.from_service_account_json(json_credentials_path=GCLOUD_PATH)
__gcloud_bucket = __gcloud_client.get_bucket(settings.GS_BUCKET_NAME)


def gc_upload_object(data, objectkey: str):

    blob_file = gc_get_blob_file(objectkey)

    if objectkey.endswith(".pdf"):
        blob_file.content_type = "application/pdf"
    elif objectkey.endswith(".jpg"):
        blob_file.content_type = "image/jpeg"
    elif objectkey.endswith(".jpeg"):
        blob_file.content_type = "image/jpeg"
    elif objectkey.endswith(".png"):
        blob_file.content_type = "image/png"
    elif objectkey.endswith(".svg"):
        blob_file.content_type = "image/svg+xml"

    return blob_file.upload_from_file(data)


def gc_get_file_url(objectkey):
    return f"{gc_get_bucket_url()}/{objectkey}"


def gc_get_bucket_url():

    bucket_url = f"{settings.GS_STORAGE_URL}/{settings.GS_BUCKET_NAME}"

    if settings.DEBUG:
        return f"{bucket_url}/dev"

    return bucket_url


def gc_delete_object(objectkey: str):

    blob_file = gc_get_blob_file(objectkey)

    if blob_file.exists():
        blob_file.delete()


def gc_list_all_objects():
    return __gcloud_bucket.list_blobs()


def gc_get_blob_file(objectkey: str):
    if settings.DEBUG:
        objectkey = f"dev/{objectkey}"

    blob_file = __gcloud_bucket.blob(objectkey)

    return blob_file


def gc_verify_file_exists(objectkey: str):
    blob_file = gc_get_blob_file(objectkey)
    return blob_file.exists()
