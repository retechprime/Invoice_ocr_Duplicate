import logging
import time
from datetime import datetime, timezone

from backend.storage.minio_client import (
    delete_object,
    get_json,
    list_objects,
    object_exists,
    put_json,
)

from .qwen_extractor import extract_with_qwen
from backend.services.web_service import get_web_service_data


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def is_rate_limit_error(exc):
    text = str(exc).lower()
    return (
        "429" in text
        or "too many requests" in text
        or "rate limit" in text
    )


def main():
    logging.info("LLM extraction worker started")

    while True:
        try:
            jobs = list_objects("jobs/extraction/")

            for job_object in jobs:
                if not job_object.endswith(".json"):
                    continue

                job = {}

                try:
                    job = get_json(job_object)

                    invoice_id = job["invoice_id"]
                    ocr_object = job["ocr_object"]

                    result_object = (
                        f"extraction/{invoice_id}/result.json"
                    )

                    status_object = (
                        f"status/{invoice_id}.json"
                    )

                    # ------------------------------------------------
                    # Skip already processed jobs
                    # ------------------------------------------------

                    if object_exists(result_object):
                        delete_object(job_object)
                        continue

                    try:
                        current_status = get_json(
                            status_object
                        )
                    except Exception:
                        current_status = {}

                    # ------------------------------------------------
                    # Start LLM processing
                    # ------------------------------------------------

                    llm_started_at = now_iso()

                    put_json(
                        status_object,
                        {
                            **current_status,
                            "invoice_id": invoice_id,
                            "status": "processing",
                            "llm_started_at": llm_started_at,
                            "error": None,
                        },
                    )

                    logging.info(
                        "Extraction processing: %s",
                        invoice_id,
                    )

                    # ------------------------------------------------
                    # Load OCR result
                    # ------------------------------------------------

                    logging.info(
                        "Loading OCR: %s",
                        ocr_object,
                    )

                    ocr = get_json(ocr_object)

                    pages = ocr.get("pages", [])

                    block_count = sum(
                        len(page.get("text", []))
                        for page in pages
                    )

                    logging.info(
                        "OCR loaded: pages=%s blocks=%s",
                        len(pages),
                        block_count,
                    )

                    # ------------------------------------------------
                    # Qwen extraction
                    # ------------------------------------------------

                    max_retries = 4
                    retry_count = 0
                    extracted = None
                    web_service_data = None

                    llm_start_time = time.perf_counter()

                    while retry_count <= max_retries:
                        try:
                            logging.info(
                                "Sending OCR to Qwen: %s",
                                invoice_id,
                            )

                            extracted = extract_with_qwen(
                                [
                                    {
                                        "page_number": page.get(
                                            "page_number"
                                        ),
                                        "text": block.get(
                                            "text",
                                            "",
                                        ),
                                    }
                                    for page in pages
                                    for block in page.get(
                                        "text",
                                        [],
                                    )
                                ]
                            )

                            # ----------------------------------------
                            # Web Service
                            # ----------------------------------------

                            web_service_data = (
                                get_web_service_data(
                                    invoice_id
                                )
                            )

                            break

                        except Exception as exc:

                            if not is_rate_limit_error(exc):
                                raise

                            retry_count += 1

                            if retry_count > max_retries:
                                raise RuntimeError(
                                    "Qwen rate limit exceeded "
                                    "after maximum retries"
                                ) from exc

                            wait_seconds = min(
                                5 * (2 ** (retry_count - 1)),
                                60,
                            )

                            logging.warning(
                                "Qwen rate limited for %s. "
                                "Retry %s/%s in %ss",
                                invoice_id,
                                retry_count,
                                max_retries,
                                wait_seconds,
                            )

                            put_json(
                                status_object,
                                {
                                    **current_status,
                                    "invoice_id": invoice_id,
                                    "status": "processing",
                                    "llm_started_at": llm_started_at,
                                    "retry_count": retry_count,
                                    "retry_reason": "rate_limit",
                                    "retry_wait_seconds": wait_seconds,
                                    "error": None,
                                },
                            )

                            time.sleep(wait_seconds)

                    # ------------------------------------------------
                    # Processing timing
                    # ------------------------------------------------

                    llm_processing_time = (
                        time.perf_counter()
                        - llm_start_time
                    )

                    llm_completed_at = now_iso()
                    completed_at = now_iso()

                    previous_start = current_status.get(
                        "queued_at"
                    )

                    total_processing_time = None

                    if previous_start:
                        try:
                            start_dt = datetime.fromisoformat(
                                previous_start
                            )

                            end_dt = datetime.fromisoformat(
                                completed_at
                            )

                            total_processing_time = round(
                                (
                                    end_dt - start_dt
                                ).total_seconds(),
                                3,
                            )

                        except Exception:
                            total_processing_time = None

                    logging.info(
                        "Qwen extraction completed: %s | "
                        "time=%.2fs | retries=%s",
                        invoice_id,
                        llm_processing_time,
                        retry_count,
                    )

                    # ------------------------------------------------
                    # Save extraction result
                    # ------------------------------------------------

                    put_json(
                        result_object,
                        {
                            "invoice_id": invoice_id,

                            "extraction": extracted,

                            "web_service_data": (
                                web_service_data
                            ),

                            "source": {
                                "ocr_object": ocr_object,
                                "pages": len(pages),
                                "ocr_blocks": block_count,
                            },

                            "processing": {
                                "llm_processing_time_seconds": round(
                                    llm_processing_time,
                                    3,
                                ),

                                "total_processing_time_seconds": (
                                    total_processing_time
                                ),

                                "retry_count": retry_count,

                                "completed_at": completed_at,
                            },
                        },
                    )

                    # ------------------------------------------------
                    # Final machine-processing status
                    # ------------------------------------------------

                    processing_done_at = now_iso()

                    put_json(
                        status_object,
                        {
                            **current_status,
                            "invoice_id": invoice_id,

                            "status": "processing_done",

                            "llm_started_at": llm_started_at,

                            "llm_completed_at": llm_completed_at,

                            "llm_processing_time_seconds": round(
                                llm_processing_time,
                                3,
                            ),

                            "processing_done_at": (
                                processing_done_at
                            ),

                            "completed_at": completed_at,

                            "processing_time_seconds": (
                                total_processing_time
                            ),

                            "pages": len(pages),

                            "retry_count": retry_count,

                            "error": None,
                        },
                    )

                    # ------------------------------------------------
                    # Job completed
                    # ------------------------------------------------

                    delete_object(job_object)

                    logging.info(
                        "Extraction + Web Service processing "
                        "completed: %s",
                        invoice_id,
                    )

                except Exception as exc:

                    logging.exception(
                        "Extraction failed: %s",
                        invoice_id
                        if job
                        else job_object,
                    )

                    try:
                        invoice_id = job.get(
                            "invoice_id"
                        )

                        if invoice_id:
                            put_json(
                                f"status/{invoice_id}.json",
                                {
                                    "invoice_id": invoice_id,
                                    "status": "extraction_failed",
                                    "failed_at": now_iso(),
                                    "error": str(exc),
                                },
                            )

                    except Exception:
                        logging.exception(
                            "Could not save failure status"
                        )

            time.sleep(2)

        except Exception as exc:

            logging.exception(
                "Worker loop failed: %s",
                exc,
            )

            time.sleep(5)


if __name__ == "__main__":
    main()