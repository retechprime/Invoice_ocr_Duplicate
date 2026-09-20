import logging
import time
from datetime import datetime, timezone

from backend.storage.minio_client import (
    get_json,
    put_json,
    list_objects,
    object_exists,
    delete_object,
)

from .processor import OCRProcessor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    logging.info("OCR worker started")

    processor = OCRProcessor()

    while True:
        try:
            jobs = list_objects("jobs/ocr/")

            for job_object in jobs:
                if not job_object.endswith(".json"):
                    continue

                try:
                    job = get_json(job_object)

                    invoice_id = job["invoice_id"]
                    original_object = job["object_name"]

                    ocr_object = (
                        f"ocr/{invoice_id}/ocr.json"
                    )

                    status_object = (
                        f"status/{invoice_id}.json"
                    )

                    if object_exists(ocr_object):
                        delete_object(job_object)
                        continue

                    ocr_started_at = now_iso()

                    logging.info(
                        "OCR processing started: %s",
                        invoice_id,
                    )

                    existing_status = {}

                    try:
                        existing_status = get_json(
                            status_object
                        )
                    except Exception:
                        pass

                    put_json(
                        status_object,
                        {
                            **existing_status,
                            "invoice_id": invoice_id,
                            "status": "processing",
                            "ocr_started_at": ocr_started_at,
                            "error": None,
                        },
                    )

                    start_time = time.perf_counter()

                    result = processor.process(
                        invoice_id=invoice_id,
                        object_name=original_object,
                    )

                    processing_time = (
                        time.perf_counter() - start_time
                    )

                    pages = result.get(
                        "pages",
                        [],
                    )

                    page_count = len(pages)

                    ocr_completed_at = now_iso()

                    logging.info(
                        "OCR completed: %s | pages=%s | time=%.2fs",
                        invoice_id,
                        page_count,
                        processing_time,
                    )

                    put_json(
                        status_object,
                        {
                            **existing_status,
                            "invoice_id": invoice_id,
                            "status": "processing",
                            "ocr_started_at": ocr_started_at,
                            "ocr_completed_at": ocr_completed_at,
                            "ocr_processing_time_seconds": round(
                                processing_time,
                                3,
                            ),
                            "pages": page_count,
                            "error": None,
                        },
                    )

                    put_json(
                        f"jobs/extraction/{invoice_id}.json",
                        {
                            "invoice_id": invoice_id,
                            "ocr_object": ocr_object,
                        },
                    )

                    delete_object(job_object)

                except Exception as exc:
                    logging.exception(
                        "OCR job failed: %s",
                        job_object,
                    )

                    try:
                        job = get_json(job_object)
                        invoice_id = job.get(
                            "invoice_id"
                        )

                        if invoice_id:
                            put_json(
                                f"status/{invoice_id}.json",
                                {
                                    "invoice_id": invoice_id,
                                    "status": "ocr_failed",
                                    "failed_at": now_iso(),
                                    "error": str(exc),
                                },
                            )
                    except Exception:
                        logging.exception(
                            "Could not save OCR failure status"
                        )

            time.sleep(2)

        except Exception:
            logging.exception(
                "OCR worker loop failed"
            )

            time.sleep(5)


if __name__ == "__main__":
    main()