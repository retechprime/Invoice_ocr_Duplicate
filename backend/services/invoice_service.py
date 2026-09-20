import os
import uuid
from datetime import datetime
from backend.storage.minio_client import put_file, put_json, get_json

def now_iso():
    return datetime.now().astimezone().isoformat()

def submit_invoice(filename: str, temp_path: str, content_type: str):
    """Store invoice, create OCR job and initialize processing status."""
    invoice_id = str(uuid.uuid4())
    extension = os.path.splitext(filename)[1].lower()
    object_name = f"original/{invoice_id}/invoice{extension}"
    timestamp = now_iso()

    put_file(object_name, temp_path, content_type)

    put_json(
        f"jobs/ocr/{invoice_id}.json",
        {
            "invoice_id": invoice_id,
            "object_name": object_name,
            "filename": filename,
            "content_type": content_type,
            "created_at": timestamp,
            "status": "queued",
        },
    )

    put_json(
        f"status/{invoice_id}.json",
        {
            "invoice_id": invoice_id,
            "filename": filename,
            "content_type": content_type,
            "object_name": object_name,
            "status": "queued",
            "uploaded_at": timestamp,
            "queued_at": timestamp,
            "ocr_started_at": None,
            "ocr_completed_at": None,
            "llm_started_at": None,
            "llm_completed_at": None,
            "processing_done_at": None,
            "reviewed_at": None,
            "approved_at": None,
            "edi_started_at": None,
            "edi_completed_at": None,
            "failed_at": None,
            "processing_time_seconds": None,
            "ocr_processing_time_seconds": None,
            "llm_processing_time_seconds": None,
            "edi_processing_time_seconds": None,
            "pages": 0,
            "retry_count": 0,
            "error": None,
        },
    )

    return {
        "invoice_id": invoice_id,
        "filename": filename,
        "status": "queued",
        "uploaded_at": timestamp,
        "object_name": object_name,
    }

def get_invoice_result(invoice_id: str):
    return get_json(f"extraction/{invoice_id}/result.json")

def get_invoice_status(invoice_id: str):
    return get_json(f"status/{invoice_id}.json")