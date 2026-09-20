from datetime import datetime
from typing import Any


class MappingResolver:

    def __init__(
        self,
        ocr_data=None,
        web_service_data=None,
        file_sequence=None,
        transaction_number=None,
        calculation_context=None,
    ):
        self.ocr_data = ocr_data or {}
        self.web_service_data = web_service_data or {}

        self.file_sequence = file_sequence
        self.transaction_number = transaction_number

        self.calculation_context = calculation_context or {}

    # ==========================================================
    # MAIN RESOLVER
    # ==========================================================

    def resolve(self, field_name, config):

        if not isinstance(config, dict):
            return ""

        # ------------------------------------------------------
        # Direct predefined value
        # ------------------------------------------------------

        if "value" in config:
            return config.get("value", "")

        mapping_type = str(config.get("type", "")).strip().upper()

        # ------------------------------------------------------
        # Type-based mappings
        # ------------------------------------------------------

        if mapping_type in {
            "SYSTEM_DATE",
            "SYSTEM DATE",
        }:
            return self._resolve_system_date(config)

        if mapping_type in {
            "SEQUENCE",
            "FILE_SEQUENCE",
            "SEQUENTIAL",
        }:
            return self._resolve_file_sequence()

        if mapping_type in {
            "TRANSACTION",
            "TRANSACTION_SEQUENCE",
        }:
            return self._resolve_transaction_number()

        if mapping_type == "CALCULATED":
            return self._resolve_calculated(field_name, config)

        # ------------------------------------------------------
        # Source
        # ------------------------------------------------------

        source = config.get("source")

        if not source:
            return ""

        source_normalized = str(source).strip().upper()

        # ------------------------------------------------------
        # Predefined / Constant
        # ------------------------------------------------------

        if source_normalized in {
            "PREDEFINED",
            "CONSTANT",
        }:
            return config.get("value", "")

        # ------------------------------------------------------
        # OCR
        # ------------------------------------------------------

        if source_normalized == "OCR":

            return self._resolve_ocr(field_name, config)

        # ------------------------------------------------------
        # WEB SERVICE
        # ------------------------------------------------------

        if source_normalized in {
            "WEB_SERVICE",
            "WEBSERVICE",
            "WEBSERVICES",
        }:

            return self._resolve_web_service(field_name, config)

        # ------------------------------------------------------
        # FILE SEQUENCE
        # ------------------------------------------------------

        if source_normalized in {
            "SEQUENCE",
            "FILE_SEQUENCE",
        }:

            return self._resolve_file_sequence()

        # ------------------------------------------------------
        # TRANSACTION
        # ------------------------------------------------------

        if source_normalized in {
            "TRANSACTION",
            "TRANSACTION_SEQUENCE",
        }:

            return self._resolve_transaction_number()

        # ------------------------------------------------------
        # SYSTEM DATE
        # ------------------------------------------------------

        if source_normalized in {
            "SYSTEM_DATE",
            "SYSTEM DATE",
        }:

            return self._resolve_system_date(config)

        # ------------------------------------------------------
        # CALCULATED
        # ------------------------------------------------------

        if source_normalized == "CALCULATED":

            return self._resolve_calculated(field_name, config)

        raise ValueError(f"Unsupported source '{source}' " f"for field '{field_name}'")

    # ==========================================================
    # OCR
    # ==========================================================

    def _resolve_ocr(self, field_name, config):

        ocr_field = config.get("ocr_field") or config.get("field_name") or field_name

        value = self._get_value(self.ocr_data, ocr_field)

        return "" if value is None else value

    # ==========================================================
    # WEB SERVICE
    # ==========================================================

    def _resolve_web_service(self, field_name, config):

        service_field = (
            config.get("service_field") or config.get("field_name") or field_name
        )

        value = self._get_value(self.web_service_data, service_field)

        return "" if value is None else value

    # ==========================================================
    # FILE SEQUENCE
    # ==========================================================

    def _resolve_file_sequence(self):

        if self.file_sequence is None:
            raise ValueError("File sequence was not initialized.")

        value = self.file_sequence

        self.file_sequence += 1

        return value

    # ==========================================================
    # TRANSACTION
    # ==========================================================

    def _resolve_transaction_number(self):

        if self.transaction_number is None:
            raise ValueError("Transaction number was not initialized.")

        return self.transaction_number

    # ==========================================================
    # SYSTEM DATE
    # ==========================================================

    def _resolve_system_date(self, config):

        date_format = config.get("format", "%Y%m%d%H%M%S")

        return datetime.now().strftime(date_format)

    # ==========================================================
    # CALCULATED
    # ==========================================================

    def _resolve_calculated(self, field_name, config):

        calculation = config.get("calculation")

        if not calculation:
            return ""

        calculation = str(calculation).strip().upper()

        # ------------------------------------------------------
        # TTAIL
        # ------------------------------------------------------

        if calculation == "COUNT_DETAIL_LINES":

            detail_lines = self.calculation_context.get("detail_lines", [])

            return len(detail_lines)

        # ------------------------------------------------------
        # FTAIL
        # ------------------------------------------------------

        if calculation == ("COUNT_FILE_LINES_EXCLUDING_FHEAD_FTAIL"):

            transaction_lines = self.calculation_context.get("transaction_lines", 0)

            return transaction_lines

        raise ValueError(
            f"Unsupported calculation " f"'{calculation}' " f"for field '{field_name}'"
        )

    # ==========================================================
    # VALUE LOOKUP
    # ==========================================================

    @staticmethod
    def _get_value(data: dict[str, Any], key):

        if not isinstance(data, dict):
            return None

        # Exact key
        if key in data:
            return data[key]

        key_string = str(key)

        # Case-insensitive key
        key_lower = key_string.lower()

        for existing_key, value in data.items():

            if str(existing_key).lower() == key_lower:
                return value

        # Nested path
        if "." in key_string:

            current = data

            for part in key_string.split("."):

                if not isinstance(current, dict):
                    return None

                found = None
                found_key = False

                for existing_key, value in current.items():

                    if str(existing_key).lower() == part.lower():
                        found = value
                        found_key = True
                        break

                if not found_key:
                    return None

                current = found

            return current

        return None
