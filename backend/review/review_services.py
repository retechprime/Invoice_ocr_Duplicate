from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.storage.minio_client import (
    get_json,
    object_exists,
    put_json,
)


REVIEW_PREFIX = "review"


def _review_path(invoice_id: str) -> str:
    """
    Returns the MinIO object path for an invoice review.
    """
    return f"{REVIEW_PREFIX}/{invoice_id}/review.json"


def _utc_now() -> str:
    """
    Return current UTC timestamp in ISO format.
    """
    return datetime.now(timezone.utc).isoformat()


def create_review(
    invoice_id: str,
    extraction_data: Optional[Dict[str, Any]] = None,
    web_service_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create the initial human-review document.

    Original OCR/Qwen extraction is preserved.

    Web Service fields remain explicitly null when the
    actual Web Service is not yet implemented.
    """

    extraction_data = extraction_data or {}

    if web_service_data is None:
        web_service_data = {
            "vendor_id": None,
            "location": None,
            "freight_type": None,
            "deal_id": None,
            "deal_approval_indicator": None,
            "upc": None,
            "item": None,
            "vpn": None,
            "original_vat_code": None,
            "original_vat_rate": None,
            "vat_code": None,
            "vat_rate": None,
            "cost_at_vat_code": None,
        }

    review_data = {
        "invoice_id": invoice_id,

        "status": "PENDING_REVIEW",

        # --------------------------------------------------------
        # ORIGINAL MACHINE-GENERATED DATA
        # --------------------------------------------------------
        # This data must remain unchanged.
        "original_extraction": extraction_data,

        # --------------------------------------------------------
        # HUMAN REVIEW DATA
        # --------------------------------------------------------
        # Human edits are stored here.
        "reviewed_data": {
            "ocr_data": extraction_data.get(
                "fields",
                {}
            ),

            "line_items": extraction_data.get(
                "line_items",
                []
            ),

            "lines": extraction_data.get(
                "lines",
                []
            ),

            "vat_lines": extraction_data.get(
                "vat_lines",
                []
            ),

            "web_service_data": web_service_data,
        },

        # --------------------------------------------------------
        # REVIEW AUDIT INFORMATION
        # --------------------------------------------------------

        "reviewed_by": None,

        "reviewed_at": None,

        "approved_at": None,
    }

    put_json(
        _review_path(invoice_id),
        review_data,
    )

    return review_data


def get_review(
    invoice_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get persisted review data for an invoice.
    """

    path = _review_path(invoice_id)

    if not object_exists(path):
        return None

    return get_json(path)


def update_review(
    invoice_id: str,
    reviewed_data: Dict[str, Any],
    reviewed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Save human-edited review data.

    The original OCR/Qwen extraction remains untouched.
    """

    review = get_review(invoice_id)

    if review is None:
        raise ValueError(
            f"Review does not exist for invoice: {invoice_id}"
        )

    review["reviewed_data"] = reviewed_data

    review["status"] = "REVIEWED"

    review["reviewed_by"] = reviewed_by

    review["reviewed_at"] = _utc_now()

    put_json(
        _review_path(invoice_id),
        review,
    )

    return review


def approve_review(
    invoice_id: str,
    reviewed_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Approve the current reviewed data.

    This function ONLY records approval.

    It does NOT generate EDI.

    EDI generation happens later in the
    EDI/background processing stage.
    """

    review = get_review(invoice_id)

    if review is None:
        raise ValueError(
            f"Review does not exist for invoice: {invoice_id}"
        )

    if review.get("status") not in {
        "PENDING_REVIEW",
        "REVIEWED",
    }:
        raise ValueError(
            "Invoice review cannot be approved "
            f"from status: {review.get('status')}"
        )

    review["status"] = "APPROVED"

    review["reviewed_by"] = (
        reviewed_by
        or review.get("reviewed_by")
    )

    review["approved_at"] = _utc_now()

    put_json(
        _review_path(invoice_id),
        review,
    )

    return review


def delete_review(
    invoice_id: str,
) -> bool:
    """
    Delete persisted review data.
    """

    path = _review_path(invoice_id)

    if not object_exists(path):
        return False

    from backend.storage.minio_client import delete_object

    delete_object(path)

    return True