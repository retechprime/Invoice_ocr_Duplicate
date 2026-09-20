# workers/extraction_worker/qwen_extractor.py

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

from huggingface_hub import InferenceClient


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

HF_MODEL = os.getenv(
    "HF_MODEL",
    "Qwen/Qwen3.8-27B",
)

HF_PROVIDER = os.getenv(
    "HF_PROVIDER",
    "cerebras",
)

HF_TOKEN = os.getenv(
    "HF_TOKEN",
    "",
)


# ============================================================
# INVOICE DICTIONARY
# ============================================================

DICTIONARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "invoice_dictionary.json"
)


def load_invoice_dictionary() -> dict:
    """
    Load invoice field aliases from:

        config/invoice_dictionary.json
    """

    if not DICTIONARY_PATH.exists():
        raise FileNotFoundError(
            f"Invoice dictionary not found: {DICTIONARY_PATH}"
        )

    try:

        with open(
            DICTIONARY_PATH,
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

    except json.JSONDecodeError as exc:

        raise ValueError(
            f"Invalid JSON in invoice dictionary: "
            f"{DICTIONARY_PATH}"
        ) from exc

    if not isinstance(data, dict):

        raise ValueError(
            "invoice_dictionary.json must contain "
            "a JSON object"
        )

    return data


INVOICE_DICTIONARY = load_invoice_dictionary()


# ============================================================
# OCR EXTRACTION FIELD MAPPINGS
# ============================================================

OCR_FIELDS = INVOICE_DICTIONARY.get(
    "ocr_extraction_fields",
    {},
)

if not isinstance(OCR_FIELDS, dict):
    OCR_FIELDS = {}


# ============================================================
# DEFAULT FIELD MAPPINGS
# ============================================================

DEFAULT_OCR_FIELDS = {

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    "currency_code": [
        "currency",
        "currency code",
        "currency type",
        "curr.",
        "currency symbol",
    ],

    "item_total_quantity": [
        "total quantity",
        "total qty",
        "total units",
        "total pieces",
        "quantity total",
    ],

    "total_discount": [
        "total discount",
        "discount total",
        "total allowance",
        "allowance total",
        "discount",
    ],

    "order_number": [
        "order number",
        "order no",
        "po number",
        "po no",
        "purchase order",
        "purchase order number",
        "customer order number",
    ],

    "document_date": [
        "document date",
        "invoice date",
        "date",
        "invoice issue date",
    ],

    "invoice_number": [
        "invoice number",
        "invoice no",
        "invoice #",
        "invoice id",
        "vendor invoice number",
        "supplier invoice number",
    ],

    "supplier_name": [
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
        "seller",
        "seller name",
        "from",
    ],

    "buyer_name": [
        "buyer",
        "buyer name",
        "customer",
        "customer name",
        "bill to",
        "sold to",
        "ship to",
    ],

    # --------------------------------------------------------
    # LINE ITEM
    # --------------------------------------------------------

    "quantity": [
        "quantity",
        "qty",
        "units",
        "pieces",
    ],

    "original_unit_cost": [
        "unit price",
        "unit cost",
        "original unit cost",
        "original price",
        "price per unit",
        "unit rate",
    ],

    "description": [
        "description",
        "item description",
        "product description",
        "product",
        "item",
        "goods description",
        "article description",
    ],

    "total_amount": [
        "amount",
        "total amount",
        "line amount",
        "line total",
        "extended amount",
        "extended price",
        "value",
        "total value",
    ],
}


def get_ocr_fields() -> dict:
    """
    JSON dictionary is the primary source.

    Missing fields are supplemented by defaults.
    """

    fields = dict(
        DEFAULT_OCR_FIELDS
    )

    for field_name, aliases in OCR_FIELDS.items():

        if not isinstance(
            aliases,
            list,
        ):
            continue

        cleaned_aliases = []

        for alias in aliases:

            if not isinstance(
                alias,
                str,
            ):
                continue

            alias = alias.strip()

            if (
                alias
                and alias not in cleaned_aliases
            ):
                cleaned_aliases.append(
                    alias
                )

        if cleaned_aliases:

            fields[field_name] = (
                cleaned_aliases
            )

    return fields


OCR_FIELDS = get_ocr_fields()


# ============================================================
# FIELD MAPPING PROMPT
# ============================================================

def build_field_mapping_prompt() -> str:
    """
    Convert dictionary mappings into prompt text.
    """

    lines = []

    for field_name, aliases in OCR_FIELDS.items():

        if not isinstance(
            aliases,
            list,
        ):
            continue

        lines.append(
            f"{field_name}:"
        )

        for alias in aliases:

            lines.append(
                f"- {alias}"
            )

        lines.append("")

    return "\n".join(lines)


FIELD_MAPPING_PROMPT = (
    build_field_mapping_prompt()
)


# ============================================================
# QWEN CLIENT
# ============================================================

if not HF_TOKEN:

    logger.warning(
        "HF_TOKEN is not configured. "
        "Qwen extraction may fail."
    )


client = InferenceClient(
    provider=HF_PROVIDER,
    api_key=HF_TOKEN,
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = f"""
You are an expert commercial invoice extraction system.

Extract the required invoice information from OCR text.

============================================================
HEADER FIELDS
============================================================

1. currency_code
2. item_total_quantity
3. total_discount
4. order_number
5. document_date
6. invoice_number
7. supplier_name
8. buyer_name

============================================================
LINE ITEM FIELDS
============================================================

For EVERY invoice line item extract:

1. description
2. quantity
3. original_unit_cost
4. total_amount

============================================================
FIELD ALIASES
============================================================

Use the following aliases from:

config/invoice_dictionary.json

{FIELD_MAPPING_PROMPT}

============================================================
IMPORTANT RULES
============================================================

1. Extract values ONLY from the supplied OCR.

2. Do NOT invent values.

3. If a header field is not found, return:

   "0.00"

4. If a line-item field is not found, return:

   "0.00"

5. supplier_name and buyer_name should remain text values
   when detected.

6. currency_code should remain a currency code such as:

   USD
   EUR
   GBP
   INR

7. If currency cannot be identified, return:

   "0.00"

8. document_date should be the invoice/document issue date.

9. Do not use due date as document_date.

10. invoice_number must be the supplier/vendor invoice number.

11. Do not confuse invoice_number with order_number.

12. order_number should use PO/order number when present.

13. description must contain the actual item/product description.

14. quantity must contain the quantity for that line item.

15. original_unit_cost must contain the unit price/cost.

16. total_amount must contain the total amount/value for that
    particular line item.

17. Do NOT use the invoice grand total as a line-item
    total_amount.

18. Preserve the value as it appears in OCR whenever possible.

19. Do NOT extract:
    - item_code
    - cartons
    - tax
    - VAT
    - net_weight
    - payment_terms
    - address
    - bank_details
    - shipping_information
    - due_date
    - exchange_rate

20. Return ALL invoice line items.

21. Do not omit a line item simply because one field is missing.

22. Missing line-item fields must be "0.00".

============================================================
ITEM TOTAL QUANTITY
============================================================

IMPORTANT:

Always populate item_total_quantity when line-item quantities
are available.

If the invoice explicitly provides a total quantity, use that
value.

If an explicit total quantity is NOT available, calculate
item_total_quantity by summing all valid line-item quantities.

Example:

Item 1 quantity = 100
Item 2 quantity = 200
Item 3 quantity = 50

item_total_quantity = 350

If there are no valid quantities anywhere in the invoice,
return:

"0.00"

Do not count the number of rows/items.

The total quantity means the SUM of the actual quantities.

============================================================
OUTPUT FORMAT
============================================================

Return EXACTLY:

{{
    "fields": {{
        "currency_code": "0.00",
        "item_total_quantity": "0.00",
        "total_discount": "0.00",
        "order_number": "0.00",
        "document_date": "0.00",
        "invoice_number": "0.00",
        "supplier_name": "0.00",
        "buyer_name": "0.00"
    }},
    "line_items": [
        {{
            "description": "0.00",
            "quantity": "0.00",
            "original_unit_cost": "0.00",
            "total_amount": "0.00"
        }}
    ]
}}

Do not add any other fields.

Return JSON only.
"""


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(
    content: str,
) -> Dict[str, Any]:
    """
    Safely extract JSON from Qwen response.
    """

    if not content:

        raise ValueError(
            "Qwen returned an empty response"
        )

    original_content = content

    content = content.strip()

    # --------------------------------------------------------
    # Remove <think>...</think>
    # --------------------------------------------------------

    content = re.sub(
        r"<think>.*?</think>",
        "",
        content,
        flags=(
            re.DOTALL
            | re.IGNORECASE
        ),
    ).strip()

    # --------------------------------------------------------
    # Remove markdown fences
    # --------------------------------------------------------

    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = re.sub(
        r"\s*```$",
        "",
        content,
        flags=re.IGNORECASE,
    ).strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:

        result = json.loads(
            content
        )

        if isinstance(
            result,
            dict,
        ):
            return result

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Find JSON object
    # --------------------------------------------------------

    start = content.find(
        "{"
    )

    end = content.rfind(
        "}"
    )

    if (
        start == -1
        or end == -1
        or end <= start
    ):

        raise ValueError(
            "Qwen response does not contain valid JSON"
        )

    json_text = content[
        start:end + 1
    ]

    try:

        result = json.loads(
            json_text
        )

    except json.JSONDecodeError as exc:

        logger.error(
            "Invalid JSON returned by Qwen"
        )

        logger.error(
            "Qwen response: %s",
            original_content,
        )

        raise ValueError(
            f"Invalid JSON returned by Qwen: {exc}"
        ) from exc

    if not isinstance(
        result,
        dict,
    ):

        raise ValueError(
            "Qwen response must be a JSON object"
        )

    return result


# ============================================================
# NORMALIZE NUMBER
# ============================================================

def parse_quantity(
    value: Any,
) -> float | None:
    """
    Convert OCR quantity into a numeric value.

    Handles:
        21585.490
        21,585.490
        21.585,490
        11,80
    """

    if value is None:
        return None

    if isinstance(
        value,
        (int, float),
    ):

        return float(value)

    text = str(
        value
    ).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # Remove currency symbols and letters
    # --------------------------------------------------------

    text = re.sub(
        r"[^\d,.\-]",
        "",
        text,
    )

    if not text:
        return None

    # --------------------------------------------------------
    # European number format
    #
    # 21.585,490 -> 21585.490
    # 11,80      -> 11.80
    # --------------------------------------------------------

    if (
        "," in text
        and "." in text
    ):

        if text.rfind(",") > text.rfind("."):

            text = text.replace(
                ".",
                "",
            )

            text = text.replace(
                ",",
                ".",
            )

    elif "," in text:

        parts = text.split(",")

        # Decimal comma
        if (
            len(parts) == 2
            and len(parts[1]) <= 3
        ):

            text = (
                parts[0]
                + "."
                + parts[1]
            )

        else:

            text = text.replace(
                ",",
                "",
            )

    try:

        return float(
            text
        )

    except ValueError:

        return None


# ============================================================
# NORMALIZE / WHITELIST
# ============================================================

def normalize_extraction(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Normalize Qwen output.

    Missing fields become "0.00".

    item_total_quantity is always populated from the sum
    of line-item quantities when possible.
    """

    if not isinstance(
        result,
        dict,
    ):
        result = {}

    fields = result.get(
        "fields",
        {},
    )

    if not isinstance(
        fields,
        dict,
    ):
        fields = {}

    # ========================================================
    # HEADER FIELDS
    # ========================================================

    clean_fields = {

        "currency_code":
            fields.get(
                "currency_code"
            ) or "0.00",

        "item_total_quantity":
            fields.get(
                "item_total_quantity"
            ) or "0.00",

        "total_discount":
            fields.get(
                "total_discount"
            ) or "0.00",

        "order_number":
            fields.get(
                "order_number"
            ) or "0.00",

        "document_date":
            fields.get(
                "document_date"
            ) or "0.00",

        "invoice_number":
            fields.get(
                "invoice_number"
            ) or "0.00",

        "supplier_name":
            fields.get(
                "supplier_name"
            ) or "0.00",

        "buyer_name":
            fields.get(
                "buyer_name"
            ) or "0.00",
    }

    # ========================================================
    # LINE ITEMS
    # ========================================================

    clean_line_items = []

    line_items = result.get(
        "line_items",
        [],
    )

    if isinstance(
        line_items,
        list,
    ):

        for item in line_items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            clean_line_items.append(
                {
                    "description":
                        item.get(
                            "description"
                        ) or "0.00",

                    "quantity":
                        item.get(
                            "quantity"
                        ) or "0.00",

                    "original_unit_cost":
                        item.get(
                            "original_unit_cost"
                        ) or "0.00",

                    "total_amount":
                        item.get(
                            "total_amount"
                        ) or "0.00",
                }
            )

    # ========================================================
    # CALCULATE ITEM TOTAL QUANTITY
    # ========================================================
    #
    # ALWAYS use line-item quantities when available.
    #
    # Example:
    #
    # 100 + 200 + 50 = 350
    #
    # If no valid quantity exists:
    #
    # item_total_quantity = "0.00"
    #
    # ========================================================

    quantity_values = []

    for item in clean_line_items:

        quantity = item.get(
            "quantity"
        )

        numeric_quantity = (
            parse_quantity(
                quantity
            )
        )

        if numeric_quantity is not None:

            quantity_values.append(
                numeric_quantity
            )

    if quantity_values:

        total_quantity = sum(
            quantity_values
        )

        # ----------------------------------------------------
        # Preserve useful decimal precision
        # ----------------------------------------------------

        if total_quantity.is_integer():

            clean_fields[
                "item_total_quantity"
            ] = str(
                int(total_quantity)
            )

        else:

            clean_fields[
                "item_total_quantity"
            ] = f"{total_quantity:.3f}"

    else:

        # ----------------------------------------------------
        # If there are no valid line quantities,
        # preserve an explicit header total if present.
        # Otherwise use 0.00.
        # ----------------------------------------------------

        explicit_total = (
            fields.get(
                "item_total_quantity"
            )
        )

        if explicit_total:

            clean_fields[
                "item_total_quantity"
            ] = explicit_total

        else:

            clean_fields[
                "item_total_quantity"
            ] = "0.00"

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    return {
        "fields": clean_fields,
        "line_items": clean_line_items,
    }


# ============================================================
# MAIN INVOICE EXTRACTION
# ============================================================

def extract_invoice(
    ocr_text: str,
) -> Dict[str, Any]:
    """
    Send OCR text to Qwen and return restricted
    invoice extraction JSON.
    """

    if not ocr_text:

        raise ValueError(
            "OCR text is empty"
        )

    if not HF_TOKEN:

        raise RuntimeError(
            "HF_TOKEN is not configured"
        )

    # ========================================================
    # USER PROMPT
    # ========================================================

    payload = f"""
Extract the invoice information from the following OCR text.

IMPORTANT:

- Extract all invoice line items.
- For every item extract description.
- For every item extract quantity.
- For every item extract original unit cost.
- For every item extract total amount.
- Missing values must be "0.00".
- item_total_quantity must represent the SUM of all
  line-item quantities.
- Return JSON only.

============================================================
OCR TEXT
============================================================

{ocr_text}
"""

    logger.info(
        "Sending invoice OCR to Qwen"
    )

    logger.info(
        "Model: %s",
        HF_MODEL,
    )

    logger.info(
        "Provider: %s",
        HF_PROVIDER,
    )

    logger.info(
        "Dictionary: %s",
        DICTIONARY_PATH,
    )

    # ========================================================
    # CALL QWEN
    # ========================================================

    try:

        response = (
            client
            .chat
            .completions
            .create(
                model=HF_MODEL,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": payload,
                    },
                ],
            )
        )

    except Exception as exc:

        logger.exception(
            "Qwen inference failed"
        )

        raise RuntimeError(
            f"Qwen inference failed: {exc}"
        ) from exc

    # ========================================================
    # READ RESPONSE
    # ========================================================

    try:

        content = (
            response
            .choices[0]
            .message
            .content
        )

    except Exception as exc:

        raise RuntimeError(
            "Unexpected Qwen response structure"
        ) from exc

    logger.info(
        "Qwen response received: %d characters",
        len(
            content or ""
        ),
    )

    # ========================================================
    # PARSE
    # ========================================================

    result = extract_json(
        content
    )

    # ========================================================
    # NORMALIZE
    # ========================================================

    return normalize_extraction(
        result
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def extract(
    ocr_text: str,
) -> Dict[str, Any]:
    """
    Backward-compatible extraction function.
    """

    return extract_invoice(
        ocr_text
    )


# ============================================================
# WORKER FUNCTION
# ============================================================

def extract_with_qwen(
    ocr_blocks,
) -> Dict[str, Any]:
    """
    Function expected by:

        workers/extraction_worker/worker.py

    Converts OCR blocks into text and sends them
    through the Qwen extraction pipeline.
    """

    if ocr_blocks is None:

        raise ValueError(
            "OCR blocks are empty"
        )

    # --------------------------------------------------------
    # OCR already supplied as text
    # --------------------------------------------------------

    if isinstance(
        ocr_blocks,
        str,
    ):

        ocr_text = ocr_blocks

    # --------------------------------------------------------
    # OCR supplied as list/dict
    # --------------------------------------------------------

    else:

        try:

            ocr_text = json.dumps(
                ocr_blocks,
                ensure_ascii=False,
                indent=2,
            )

        except Exception as exc:

            raise ValueError(
                f"Unable to serialize OCR blocks: {exc}"
            ) from exc

    # --------------------------------------------------------
    # Execute extraction
    # --------------------------------------------------------

    return extract_invoice(
        ocr_text
    )