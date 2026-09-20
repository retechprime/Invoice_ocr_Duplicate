import logging
from datetime import datetime
from backend.storage.minio_client import get_json, object_exists, put_json
from backend.services.edi_mapping_service import EDIMappingService

logger = logging.getLogger(__name__)

STATUS_PREFIX = "status"
REVIEW_PREFIX = "review"
EDI_PREFIX = "edi"

def _status_path(invoice_id: str) -> str:
    return f"{STATUS_PREFIX}/{invoice_id}.json"

def _review_path(invoice_id: str) -> str:
    return f"{REVIEW_PREFIX}/{invoice_id}/review.json"

def _edi_path(invoice_id: str) -> str:
    return f"{EDI_PREFIX}/{invoice_id}/result.json"

def _load_status(invoice_id: str):
    path = _status_path(invoice_id)
    if not object_exists(path):
        return None
    return get_json(path)

def _load_review(invoice_id: str):
    path = _review_path(invoice_id)
    if not object_exists(path):
        return None
    return get_json(path)

def _save_status(invoice_id: str, status: dict):
    put_json(_status_path(invoice_id), status)

class EDIProcessor:
    def __init__(self):
        self.mapping_service = EDIMappingService()

    async def process(self, invoice_id: str):
        logger.info("Starting EDI processing: %s", invoice_id)

        status = _load_status(invoice_id)
        if not status:
            raise ValueError(f"Invoice not found: {invoice_id}")

        if str(status.get("status", "")).lower() != "approved":
            raise ValueError(
                f"Invoice is not approved: {status.get('status')}"
            )

        review = _load_review(invoice_id)
        if not review:
            raise ValueError(f"Review not found: {invoice_id}")

        reviewed_data = review.get("reviewed_data")
        if not isinstance(reviewed_data, dict):
            raise ValueError("Invalid reviewed_data")

        ocr_data = reviewed_data.get("ocr_data") or {}
        line_items = reviewed_data.get("line_items") or []
        lines = reviewed_data.get("lines") or []
        vat_lines = reviewed_data.get("vat_lines") or []
        web_service_data = reviewed_data.get("web_service_data")

        # Web Service is not implemented yet.
        if web_service_data is None:
            web_service_data = {}

        ocr_payload = {
            **ocr_data,
            "line_items": line_items,
            "lines": lines,
            "vat_lines": vat_lines,
        }

        status["status"] = "edi_processing"
        status["stage"] = "edi_processing"
        status["error"] = None
        status["edi_processing_started_at"] = datetime.now().isoformat()
        _save_status(invoice_id, status)

        try:
            result = self.mapping_service.generate_edi(
                ocr_data=ocr_payload,
                web_service_data=web_service_data,
            )

            edi_result = {
                "invoice_id": invoice_id,
                "status": "generated",
                "format": "EDI801",
                "generated_at": datetime.now().isoformat(),
                "result": result,
            }

            put_json(_edi_path(invoice_id), edi_result)

            status["status"] = "edi_generated"
            status["stage"] = "edi_generated"
            status["edi_generated_at"] = datetime.now().isoformat()
            status["error"] = None
            _save_status(invoice_id, status)

            logger.info("EDI generated successfully: %s", invoice_id)
            return edi_result

        except Exception as exc:
            logger.exception("EDI generation failed: %s", invoice_id)

            status["status"] = "edi_failed"
            status["stage"] = "edi_failed"
            status["error"] = str(exc)
            status["edi_failed_at"] = datetime.now().isoformat()
            _save_status(invoice_id, status)

            raise