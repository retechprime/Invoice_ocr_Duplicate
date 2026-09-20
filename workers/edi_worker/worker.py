import logging
import os
import tempfile
import time
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.storage.minio_client import (
    get_json,
    object_exists,
    put_file,
    put_json,
)
from backend.services.edi_mapping_service import EDIMappingService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def generate_edi_pdf(invoice_id: str, edi_text: str):
    """
    Generate an EDI 801 PDF from the generated EDI text
    and upload it to MinIO.
    """

    pdf_object = f"edi/{invoice_id}/edi_801.pdf"

    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    ) as tmp:
        pdf_path = tmp.name

    try:
        pdf = canvas.Canvas(
            pdf_path,
            pagesize=A4,
        )

        width, height = A4

        pdf.setFont("Courier", 8)

        y = height - 40

        for line in edi_text.splitlines():

            # Start a new page when the current page is full.
            if y < 40:
                pdf.showPage()
                pdf.setFont("Courier", 8)
                y = height - 40

            pdf.drawString(
                30,
                y,
                line,
            )

            y -= 10

        pdf.save()

        # Upload generated PDF to MinIO.
        put_file(
            pdf_object,
            pdf_path,
            "application/pdf",
        )

        logging.info(
            "EDI PDF uploaded successfully: %s",
            pdf_object,
        )

        return pdf_object

    finally:
        # Remove temporary local PDF file.
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def main():
    logging.info("EDI worker started")

    mapping_service = EDIMappingService()

    while True:
        try:
            jobs = []

            # Find invoices approved by human review.
            for status_object in list_status_objects():

                if not status_object.endswith(".json"):
                    continue

                invoice_id = (
                    status_object
                    .split("/")[-1]
                    .replace(".json", "")
                )

                status = get_json(status_object)

                if (
                    str(status.get("status", "")).lower()
                    != "approved"
                ):
                    continue

                jobs.append(
                    (
                        invoice_id,
                        status_object,
                        status,
                    )
                )

            for invoice_id, status_object, status in jobs:

                edi_object = (
                    f"edi/{invoice_id}/result.json"
                )

                review_object = (
                    f"review/{invoice_id}/review.json"
                )

                # Do not process an already generated EDI.
                if object_exists(edi_object):
                    continue

                # Approved invoice must have review data.
                if not object_exists(review_object):
                    logging.warning(
                        "Review not found for approved invoice: %s",
                        invoice_id,
                    )
                    continue

                try:
                    # -------------------------------------------------
                    # 1. Load human-reviewed data
                    # -------------------------------------------------

                    review = get_json(review_object)

                    reviewed_data = review.get(
                        "reviewed_data"
                    )

                    if not isinstance(reviewed_data, dict):
                        raise ValueError(
                            "Invalid reviewed_data"
                        )

                    ocr_data = (
                        reviewed_data.get("ocr_data")
                        or {}
                    )

                    line_items = (
                        reviewed_data.get("line_items")
                        or []
                    )

                    lines = (
                        reviewed_data.get("lines")
                        or []
                    )

                    vat_lines = (
                        reviewed_data.get("vat_lines")
                        or []
                    )

                    # -------------------------------------------------
                    # 2. Web Service data
                    # -------------------------------------------------
                    # Web Service is not implemented yet.
                    # Therefore all Web Service fields remain null.

                    web_service_data = (
                        reviewed_data.get(
                            "web_service_data"
                        )
                    )

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

                    # -------------------------------------------------
                    # 3. Build OCR payload
                    # -------------------------------------------------

                    ocr_payload = {
                        **ocr_data,
                        "line_items": line_items,
                        "lines": lines,
                        "vat_lines": vat_lines,
                    }

                    # -------------------------------------------------
                    # 4. Mark EDI processing
                    # -------------------------------------------------

                    edi_started_at = now_iso()

                    put_json(
                        status_object,
                        {
                            **status,
                            "status": "edi_processing",
                            "edi_started_at": edi_started_at,
                            "edi_completed_at": None,
                            "error": None,
                        },
                    )

                    logging.info(
                        "EDI processing started: %s",
                        invoice_id,
                    )

                    # -------------------------------------------------
                    # 5. Generate EDI 801
                    # -------------------------------------------------

                    result = mapping_service.generate_edi(
                        ocr_data=ocr_payload,
                        web_service_data=web_service_data,
                    )

                    # Make sure EDI text exists.
                    edi_text = result.get("edi_text")

                    if not edi_text:
                        raise ValueError(
                            "EDI generation returned empty edi_text"
                        )

                    # -------------------------------------------------
                    # 6. Save EDI result JSON
                    # -------------------------------------------------

                    edi_result = {
                        "invoice_id": invoice_id,
                        "status": "generated",
                        "format": "EDI801",
                        "generated_at": now_iso(),
                        "result": result,
                    }

                    put_json(
                        edi_object,
                        edi_result,
                    )

                    # -------------------------------------------------
                    # 7. Generate EDI PDF
                    # -------------------------------------------------

                    edi_pdf_object = generate_edi_pdf(
                        invoice_id,
                        edi_text,
                    )

                    logging.info(
                        "EDI PDF generated: %s",
                        edi_pdf_object,
                    )

                    # -------------------------------------------------
                    # 8. Mark invoice as EDI generated
                    # -------------------------------------------------

                    edi_completed_at = now_iso()

                    put_json(
                        status_object,
                        {
                            **status,
                            "status": "edi_generated",
                            "edi_started_at": edi_started_at,
                            "edi_completed_at": edi_completed_at,
                            "error": None,
                        },
                    )

                    logging.info(
                        "EDI generated successfully: %s",
                        invoice_id,
                    )

                except Exception as exc:

                    logging.exception(
                        "EDI processing failed: %s",
                        invoice_id,
                    )

                    put_json(
                        status_object,
                        {
                            **status,
                            "status": "edi_failed",
                            "failed_at": now_iso(),
                            "error": str(exc),
                        },
                    )

            # Poll every 2 seconds.
            time.sleep(2)

        except Exception as exc:

            logging.exception(
                "EDI worker loop failed: %s",
                exc,
            )

            time.sleep(5)


def list_status_objects():
    from backend.storage.minio_client import list_objects

    return list_objects("status/")


if __name__ == "__main__":
    main()