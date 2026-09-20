import io
import json

from minio import Minio

from backend.core.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    MINIO_SECURE,
)

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)


def ensure_bucket():
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


def put_file(
    object_name,
    path,
    content_type="application/octet-stream",
):
    ensure_bucket()

    client.fput_object(
        MINIO_BUCKET,
        object_name,
        path,
        content_type=content_type,
    )

    return object_name


def get_file(object_name, path):
    ensure_bucket()

    client.fget_object(
        MINIO_BUCKET,
        object_name,
        path,
    )

    return path


def put_json(object_name, data):
    ensure_bucket()

    raw = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    client.put_object(
        MINIO_BUCKET,
        object_name,
        io.BytesIO(raw),
        len(raw),
        content_type="application/json",
    )

    return object_name


def get_json(object_name):
    ensure_bucket()

    response = client.get_object(
        MINIO_BUCKET,
        object_name,
    )

    try:
        return json.loads(
            response.read().decode("utf-8")
        )
    finally:
        response.close()
        response.release_conn()


def list_objects(prefix=""):
    ensure_bucket()

    return [
        obj.object_name
        for obj in client.list_objects(
            MINIO_BUCKET,
            prefix=prefix,
            recursive=True,
        )
    ]


def object_exists(object_name):
    ensure_bucket()

    try:
        client.stat_object(
            MINIO_BUCKET,
            object_name,
        )
        return True
    except Exception:
        return False


def delete_object(object_name):
    ensure_bucket()

    client.remove_object(
        MINIO_BUCKET,
        object_name,
    )