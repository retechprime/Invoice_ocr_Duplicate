from typing import Dict, Any


# ============================================================
# WEB SERVICE PLACEHOLDER
# ============================================================

def get_web_service_data(invoice_id: str) -> Dict[str, Any]:
    """
    Temporary Web Service integration.

    The actual Web Service has not been implemented yet.

    Until the real Web Service is connected, all Web Service
    fields are returned as None.

    Args:
        invoice_id: Unique invoice identifier.

    Returns:
        Dictionary containing all expected Web Service fields.
    """

    return {
        # ----------------------------------------------------
        # Vendor / Location
        # ----------------------------------------------------
        "vendor_id": None,
        "location": None,

        # ----------------------------------------------------
        # Deal / Freight
        # ----------------------------------------------------
        "freight_type": None,
        "deal_id": None,
        "deal_approval_indicator": None,

        # ----------------------------------------------------
        # Item Information
        # ----------------------------------------------------
        "upc": None,
        "item": None,
        "vpn": None,

        # ----------------------------------------------------
        # Original VAT Information
        # ----------------------------------------------------
        "original_vat_code": None,
        "original_vat_rate": None,

        # ----------------------------------------------------
        # VAT Information
        # ----------------------------------------------------
        "vat_code": None,
        "vat_rate": None,

        # ----------------------------------------------------
        # Cost / VAT
        # ----------------------------------------------------
        "cost_at_vat_code": None,
    }