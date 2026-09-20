import math

import os

import tempfile

from datetime import datetime

from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from fastapi.responses import FileResponse, Response

from starlette.background import BackgroundTask

from backend.services.invoice_service import submit_invoice

from backend.services.edi_mapping_service import EDIMappingService

from fastapi.responses import StreamingResponse

from backend.review.review_services import (
    create_review,
    get_review as get_saved_review,
    update_review,
    approve_review,
)

from backend.storage.minio_client import (
    delete_object,
    get_file,
    get_json,
    list_objects,
    object_exists,
    put_json,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

# MinIO helpers


def load_status(invoice_id: str) -> dict:

    try:

        return get_json(f"status/{invoice_id}.json")

    except Exception:

        return {}


def load_result(invoice_id: str) -> dict | None:

    try:

        return get_json(f"extraction/{invoice_id}/result.json")

    except Exception:

        return None


def load_edi_result(invoice_id: str) -> dict | None:

    try:

        return get_json(f"edi/{invoice_id}/result.json")

    except Exception:

        return None


def save_status(invoice_id: str, status_data: dict) -> None:

    put_json(f"status/{invoice_id}.json", status_data)


# Generic helpers


def value_from_field(field: Any) -> Any:

    if isinstance(field, dict):

        return field.get("value")

    return field


def _normalise_key(value: Any) -> str:

    return str(value).strip().lower().replace("_", " ").replace("-", " ")


def _flatten_fields(fields: dict) -> dict:

    data = {}

    if not isinstance(fields, dict):

        return data

    for key, field in fields.items():

        value = value_from_field(field)

        data[key] = value

    aliases = {
        "invoice number": "invoice_number",
        "invoice no": "invoice_number",
        "invoice #": "invoice_number",
        "document number": "invoice_number",
        "document date": "document_date",
        "invoice date": "document_date",
        "vendor document date": "document_date",
        "order number": "order_number",
        "po number": "order_number",
        "purchase order": "order_number",
        "currency": "currency_code",
        "currency code": "currency_code",
        "total quantity": "total_quantity",
        "quantity total": "total_quantity",
        "total discount": "total_discount",
        "discount": "total_discount",
        "supplier name": "supplier_name",
        "supplier": "supplier_name",
        "seller": "supplier_name",
        "vendor name": "supplier_name",
        "vendor": "supplier_name",
        "buyer name": "buyer_name",
        "buyer": "buyer_name",
        "customer name": "buyer_name",
        "customer": "buyer_name",
        "quantity": "quantity",
        "original unit cost": "original_unit_cost",
        "unit cost": "original_unit_cost",
        "unit price": "original_unit_cost",
    }

    for key, field in fields.items():

        normalised = _normalise_key(key)

        canonical = aliases.get(normalised)

        if canonical:

            data[canonical] = value_from_field(field)

    return data


def _prepare_mapping_data(result_data: dict) -> tuple[dict, dict]:

    extraction = result_data.get("extraction", {})

    if not isinstance(extraction, dict):

        extraction = {}

    fields = extraction.get("fields", {}) or {}

    # OCR fields

    ocr_data = _flatten_fields(fields)

    # Preserve line/vat structures because TDETL/TVATS are downstream

    # mapping records, not part of the OCR worker.

    line_items = (
        extraction.get("line_items")
        or extraction.get("lines")
        or result_data.get("line_items")
        or result_data.get("lines")
        or []
    )

    vat_lines = extraction.get("vat_lines") or result_data.get("vat_lines") or []

    ocr_data["line_items"] = line_items

    ocr_data["lines"] = line_items

    ocr_data["vat_lines"] = vat_lines

    # Web Service result can be stored at the result level or inside

    # extraction. We only read existing service output; we do not invent it.

    web_service_data = (
        result_data.get("web_service_data")
        or result_data.get("web_services")
        or result_data.get("webservice_data")
        or extraction.get("web_service_data")
        or extraction.get("web_services")
        or {}
    )

    if not isinstance(web_service_data, dict):

        web_service_data = {}

    return ocr_data, web_service_data


# Invoice summary


def extract_summary(
    invoice_id: str,
    status_data: dict | None = None,
    result_data: dict | None = None,
) -> dict:

    status_data = status_data or load_status(invoice_id)

    result_data = result_data if result_data is not None else load_result(invoice_id)

    extraction = (
        result_data.get("extraction", {}) if isinstance(result_data, dict) else {}
    )

    fields = extraction.get("fields", {}) or {}

    totals = extraction.get("totals", {}) or {}

    invoice_number = None

    supplier = None

    total = None

    confidence_values = []

    for label, field in fields.items():

        if not isinstance(field, dict):

            continue

        value = field.get("value")

        confidence = field.get("confidence")

        if isinstance(confidence, (int, float)):

            confidence_values.append(float(confidence))

        key = str(label).lower()

        if invoice_number is None and any(
            x in key
            for x in (
                "invoice no",
                "invoice number",
                "invoice #",
                "invoice id",
            )
        ):

            invoice_number = value

        if supplier is None and any(
            x in key
            for x in (
                "shipper",
                "exporter",
                "supplier",
                "seller",
                "vendor",
            )
        ):

            supplier = value

    for label, field in totals.items():

        key = str(label).lower()

        if any(
            x in key
            for x in (
                "grand total",
                "invoice total",
                "total amount",
                "net amount",
                "total",
            )
        ):

            total = value_from_field(field)

            if total is not None:

                break

    status_display = str(status_data.get("status", "unknown"))

    filename = status_data.get("filename") or "invoice"

    processing_time = status_data.get("processing_time_seconds")

    if not isinstance(processing_time, (int, float)):

        processing_time = None

    pages = status_data.get("pages")

    if not isinstance(pages, (int, float)):

        pages = 0

    confidence = None

    if confidence_values:

        confidence = round(
            sum(confidence_values) / len(confidence_values),
            4,
        )

    return {
        "invoice_id": invoice_id,
        "filename": filename,
        "invoice_number": invoice_number,
        "supplier": supplier,
        "status": status_display,
        "stage": status_data.get("stage", ""),
        "total": total,
        "confidence": confidence,
        "pages": pages,
        "processing_time_seconds": processing_time,
        "uploaded_at": status_data.get("uploaded_at"),
        "ocr_started_at": status_data.get("ocr_started_at"),
        "ocr_completed_at": status_data.get("ocr_completed_at"),
        "llm_started_at": status_data.get("llm_started_at"),
        "llm_completed_at": status_data.get("llm_completed_at"),
        "completed_at": status_data.get("completed_at"),
        "processing_done_at": status_data.get("processing_done_at"),
        "reviewed_at": status_data.get("reviewed_at"),
        "approved_at": status_data.get("approved_at"),
        "edi_started_at": status_data.get("edi_started_at"),
        "edi_completed_at": status_data.get("edi_completed_at"),
        "error": status_data.get("error"),
        "content_type": status_data.get("content_type"),
        "retry_count": status_data.get("retry_count", 0),
    }


# Upload


@router.post("/upload")
async def upload(file: UploadFile = File(...)):

    filename = file.filename or ""

    extension = os.path.splitext(filename)[1].lower()

    if extension not in ALLOWED:

        raise HTTPException(
            status_code=400,
            detail="Unsupported file type",
        )

    fd, path = tempfile.mkstemp(suffix=extension)

    os.close(fd)

    try:

        content = await file.read()

        if not content:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        with open(path, "wb") as output:

            output.write(content)

        return submit_invoice(
            filename=filename,
            temp_path=path,
            content_type=file.content_type or "application/octet-stream",
        )

    finally:

        if os.path.exists(path):

            os.remove(path)


# Invoice list


@router.get("")
def list_invoices(
    page: int = 1,
    page_size: int = 100,
    status: str | None = None,
    search: str | None = None,
):

    try:

        invoices = []

        for object_name in list_objects("status/"):

            if not object_name.endswith(".json"):

                continue

            invoice_id = os.path.basename(object_name)[:-5]

            status_data = load_status(invoice_id)

            if not status_data:

                continue

            item = extract_summary(
                invoice_id,
                status_data,
            )

            if status and item["status"].lower() != status.lower():

                continue

            if search:

                needle = search.lower().strip()

                haystack = " ".join(
                    str(item.get(key) or "")
                    for key in (
                        "filename",
                        "invoice_number",
                        "supplier",
                    )
                ).lower()

                if needle not in haystack:

                    continue

            invoices.append(item)

        invoices.sort(
            key=lambda x: (x.get("uploaded_at") or x.get("invoice_id", "")),
            reverse=True,
        )

        total = len(invoices)

        page = max(page, 1)

        page_size = min(max(page_size, 1), 100)

        start = (page - 1) * page_size

        items = invoices[start : start + page_size]

        return {
            "items": items,
            "documents": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# Statistics


@router.get("/stats/summary")
def invoice_stats():
    total = 0
    queued = 0
    processing = 0
    processing_done = 0
    approved = 0
    edi_processing = 0
    edi_generated = 0
    failed = 0

    processing_times = []
    page_counts = []

    for object_name in list_objects("status/"):
        if not object_name.endswith(".json"):
            continue

        invoice_id = os.path.basename(object_name)[:-5]
        status_data = load_status(invoice_id)

        if not status_data:
            continue

        total += 1
        status = str(status_data.get("status", "")).lower()

        if status == "queued":
            queued += 1
        elif status == "processing":
            processing += 1
        elif status == "processing_done":
            processing_done += 1
        elif status == "approved":
            approved += 1
        elif status == "edi_processing":
            edi_processing += 1
        elif status == "edi_generated":
            edi_generated += 1
        elif status in {
            "ocr_failed",
            "extraction_failed",
            "edi_failed",
            "failed",
        }:
            failed += 1

        seconds = status_data.get("processing_time_seconds")
        if isinstance(seconds, (int, float)) and seconds >= 0:
            processing_times.append(float(seconds))

        pages = status_data.get("pages")
        if isinstance(pages, (int, float)) and pages > 0:
            page_counts.append(float(pages))

    avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_pages = sum(page_counts) / len(page_counts) if page_counts else 0

    return {
        "total": total,
        "queued": queued,
        "processing": processing,
        "processing_done": processing_done,
        "approved": approved,
        "edi_processing": edi_processing,
        "edi_generated": edi_generated,
        "failed": failed,
        "average_processing_time_seconds": round(avg_time, 2),
        "avg_processing_time_seconds": round(avg_time, 2),
        "average_pages": round(avg_pages, 2),
        "avg_pages": round(avg_pages, 2),
    }


# Status / result / review


@router.get("/{invoice_id}/status")
def get_status(invoice_id: str):

    status = load_status(invoice_id)

    if not status:

        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    return status


@router.get("/{invoice_id}/result")
def get_result(invoice_id: str):

    result = load_result(invoice_id)

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Result not available",
        )

    return result


def _prepare_reviewed_edi_payload(reviewed_data: dict) -> tuple[dict, dict]:
    """Build the same payload shape consumed by the EDI worker."""
    ocr_data = reviewed_data.get("ocr_data") or {}
    line_items = reviewed_data.get("line_items") or []
    lines = reviewed_data.get("lines") or []
    vat_lines = reviewed_data.get("vat_lines") or []

    web_service_data = reviewed_data.get("web_service_data")
    if web_service_data is None:
        web_service_data = {}

    if not isinstance(ocr_data, dict):
        raise ValueError("OCR data must be an object")
    if not isinstance(web_service_data, dict):
        raise ValueError("Web Service data must be an object")

    return (
        {
            **ocr_data,
            "line_items": line_items,
            "lines": lines,
            "vat_lines": vat_lines,
        },
        web_service_data,
    )


def _edi_validation_message(exc: Exception) -> str:
    """Convert generator errors into a concise, actionable UI message."""
    message = str(exc)
    import re

    match = re.search(r"Invalid numeric value for '([^']+)': (.+)$", message)
    if match:
        field = match.group(1)
        received = match.group(2)
        labels = {
            "order_number": "Order Number",
            "vendor_id": "Vendor ID",
            "location": "Location",
            "original_document_quantity": "Original Document Quantity",
            "original_unit_cost": "Original Unit Cost",
            "original_vat_rate": "Original VAT Rate",
            "total_quantity": "Total Quantity",
            "total_discount": "Total Discount",
            "exchange_rate": "Exchange Rate",
            "total_cost": "Total Cost",
            "total_vat_amount": "Total VAT Amount",
        }
        label = labels.get(field, field)
        return (
            f"{label} is invalid. Received: '{received}'. "
            "Expected: numeric digits only; the EDI generator will zero-pad "
            "the value to the field's fixed length."
        )

    match = re.search(r"Invalid date value for '([^']+)': (.+)\. Expected", message)
    if match:
        field = match.group(1)
        received = match.group(2)
        label = {
            "vendor_document_date": "Vendor Document Date",
            "DUE_DATE": "Due Date",
        }.get(field, field)
        return (
            f"{label} is invalid. Received: '{received}'. "
            "Expected: a valid date that can be serialized as "
            "YYYYMMDDHH24MISS (14 characters)."
        )

    return message


@router.post("/{invoice_id}/approve")
def approve_invoice(
    invoice_id: str,
    body: dict | None = Body(default=None),
):
    status = load_status(invoice_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    review = get_saved_review(invoice_id)

    if review is None:
        raise HTTPException(
            status_code=409,
            detail="Invoice review is not available",
        )

    current_status = str(status.get("status", "")).lower()

    if current_status == "approved":
        raise HTTPException(
            status_code=409,
            detail="Invoice is already approved",
        )

    # Normal approval starts at processing_done. After an EDI failure,
    # the user is allowed back into review to correct the data and retry.
    if current_status not in {"processing_done", "edi_failed", "edi_generated"}:
        raise HTTPException(
            status_code=409,
            detail=(
                "Invoice is not ready for approval. "
                f"Current status: {current_status or 'unknown'}"
            ),
        )

    review_status = str(review.get("status", "")).upper()

    if review_status not in {
        "PENDING_REVIEW",
        "REVIEWED",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Review must be saved again before approval. "
                f"Current review status: {review_status or 'unknown'}"
            ),
        )

    if not isinstance(
        review.get("reviewed_data"),
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail="Reviewed data is invalid",
        )

    reviewed_by = None

    if body:
        reviewed_by = body.get("reviewed_by")

    # Validate with the exact same EDI generator used by the worker.
    # This prevents an invoice from entering APPROVED when EDI serialization
    # would fail later.
    try:
        ocr_payload, web_service_data = _prepare_reviewed_edi_payload(
            review["reviewed_data"]
        )
        validator = EDIMappingService()
        validation_result = validator.generate_edi(
            ocr_data=ocr_payload,
            web_service_data=web_service_data,
        )
        if not isinstance(validation_result, dict) or not validation_result.get(
            "edi_text"
        ):
            raise ValueError("EDI validation returned no EDI text")
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": _edi_validation_message(exc),
                "received": str(exc),
                "hint": "Correct the value in the review page and approve again.",
            },
        )

    # Approve review
    try:
        approved_review = approve_review(
            invoice_id=invoice_id,
            reviewed_by=reviewed_by,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    # Remove stale EDI artifacts before retrying a failed EDI job.
    if current_status in {"edi_failed", "edi_generated"}:
        for object_name in (
            f"edi/{invoice_id}/result.json",
            f"edi/{invoice_id}/edi_801.pdf",
        ):
            try:
                if object_exists(object_name):
                    delete_object(object_name)
            except Exception:
                pass

    # Update invoice status
    now = datetime.now().astimezone().isoformat()

    status["status"] = "approved"
    status["approved_at"] = now
    status["error"] = None
    status["edi_started_at"] = None
    status["edi_completed_at"] = None
    status["retry_count"] = int(status.get("retry_count", 0)) + 1

    save_status(
        invoice_id,
        status,
    )

    return {
        "invoice_id": invoice_id,
        "status": "approved",
        "message": ("Invoice approved. " "EDI processing can now start."),
        "review": approved_review,
    }


# EDI result


@router.get("/{invoice_id}/edi")
def get_edi(invoice_id: str):

    status = load_status(invoice_id)

    if not status:

        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    edi_result = load_edi_result(invoice_id)

    if edi_result is None:

        raise HTTPException(
            status_code=404,
            detail="EDI result not available",
        )

    return edi_result


# Download EDI JSON


@router.get("/{invoice_id}/edi/download")
def download_edi_json(invoice_id: str):

    status = load_status(invoice_id)

    if not status:

        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    if str(status.get("status", "")).lower() != "edi_generated":

        raise HTTPException(
            status_code=409,
            detail="EDI is available only after EDI generation is complete",
        )

    edi_result = load_edi_result(invoice_id)

    if edi_result is None:

        raise HTTPException(
            status_code=404,
            detail="EDI result not available",
        )

    return Response(
        content=__import__("json").dumps(
            edi_result,
            ensure_ascii=False,
            indent=2,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (f'attachment; filename="{invoice_id}_EDI801.json"')
        },
    )


# Download actual fixed-width EDI 801


@router.get("/{invoice_id}/edi/download-fixed")
def download_edi_fixed(invoice_id: str):

    status = load_status(invoice_id)

    if not status:

        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    if str(status.get("status", "")).lower() != "edi_generated":

        raise HTTPException(
            status_code=409,
            detail="EDI is available only after EDI generation is complete",
        )

    edi_result = load_edi_result(invoice_id)

    if edi_result is None:

        raise HTTPException(
            status_code=404,
            detail="EDI result not available",
        )

    edi_payload = edi_result.get("result", edi_result)
    edi_text = edi_payload.get("edi_text") if isinstance(edi_payload, dict) else None

    if not isinstance(edi_text, str) or not edi_text.strip():
        raise HTTPException(
            status_code=500,
            detail="Fixed-width EDI text is missing",
        )

    return Response(
        content=edi_text,
        media_type="text/plain",
        headers={
            "Content-Disposition": (f'attachment; filename="{invoice_id}_EDI801.txt"')
        },
    )


# OCR result


@router.get("/{invoice_id}/ocr")
def get_ocr(invoice_id: str):

    try:

        return get_json(f"ocr/{invoice_id}/ocr.json")

    except Exception:

        raise HTTPException(
            status_code=404,
            detail="OCR result not available",
        )


# Original invoice file


@router.get("/{invoice_id}/file")
def get_invoice_file(invoice_id: str):

    status = load_status(invoice_id)

    object_name = status.get("object_name") if status else None

    if not object_name:

        for extension in sorted(ALLOWED):

            candidate = f"original/{invoice_id}/invoice{extension}"

            if object_exists(candidate):

                object_name = candidate

                break

    if not object_name:

        raise HTTPException(
            status_code=404,
            detail="Original invoice not found",
        )

    extension = os.path.splitext(object_name)[1].lower()

    content_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }

    fd, temp_path = tempfile.mkstemp(suffix=extension)

    os.close(fd)

    try:

        get_file(
            object_name,
            temp_path,
        )

        return FileResponse(
            temp_path,
            media_type=content_types.get(
                extension,
                "application/octet-stream",
            ),
            filename=os.path.basename(object_name),
            background=BackgroundTask(
                os.remove,
                temp_path,
            ),
        )

    except Exception as exc:

        if os.path.exists(temp_path):

            os.remove(temp_path)

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


# Delete invoice and all generated artifacts


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: str):

    prefixes = [
        f"original/{invoice_id}/",
        f"ocr/{invoice_id}/",
        f"extraction/{invoice_id}/",
        f"edi/{invoice_id}/",
        f"review/{invoice_id}/",
        f"status/{invoice_id}.json",
        f"jobs/ocr/{invoice_id}.json",
        f"jobs/extraction/{invoice_id}.json",
    ]

    deleted = 0

    for prefix in prefixes:

        for object_name in list_objects(prefix):

            delete_object(object_name)

            deleted += 1

    return {
        "invoice_id": invoice_id,
        "deleted": True,
        "deleted_objects": deleted,
    }


@router.get("/{invoice_id}/review")
def get_invoice_review(invoice_id: str):

    status = load_status(invoice_id)

    result = load_result(invoice_id)

    if not status:

        raise HTTPException(status_code=404, detail="Invoice not found")

    if result is None:

        raise HTTPException(status_code=404, detail="Invoice result not available")

    existing_review = get_saved_review(invoice_id)

    if existing_review is not None:

        return {"invoice_id": invoice_id, "status": status, "review": existing_review}

    extraction = result.get("extraction", result)

    web_service_data = result.get("web_service_data")

    if web_service_data is None:

        web_service_data = (
            extraction.get("web_service_data")
            or extraction.get("web_services")
            or extraction.get("webservice_data")
        )

    review = create_review(
        invoice_id=invoice_id,
        extraction_data=extraction,
        web_service_data=web_service_data,
    )

    return {"invoice_id": invoice_id, "status": status, "review": review}


@router.put("/{invoice_id}/review")
def save_invoice_review(invoice_id: str, body: dict = Body(...)):

    status = load_status(invoice_id)

    if not status:

        raise HTTPException(status_code=404, detail="Invoice not found")

    review = get_saved_review(invoice_id)

    if review is None:

        raise HTTPException(status_code=404, detail="Review has not been created yet")

    reviewed_data = body.get("reviewed_data")

    if reviewed_data is None:

        raise HTTPException(status_code=400, detail="reviewed_data is required")

    try:

        updated_review = update_review(
            invoice_id=invoice_id,
            reviewed_data=reviewed_data,
            reviewed_by=body.get("reviewed_by"),
        )

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc))

    return {"invoice_id": invoice_id, "status": "REVIEWED", "review": updated_review}


@router.get("/{invoice_id}/edi/download")
def download_edi_pdf(invoice_id: str):
    pdf_object = f"edi/{invoice_id}/edi_801.pdf"

    if not object_exists(pdf_object):
        raise HTTPException(status_code=404, detail="EDI PDF not found")

    pdf_data = get_file(pdf_object)

    return StreamingResponse(
        pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (f'attachment; filename="EDI_801_{invoice_id}.pdf"')
        },
    )
