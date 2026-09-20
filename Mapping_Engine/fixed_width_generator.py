from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re


class FixedWidthGenerator:

    def __init__(self, strict=True):
        self.strict = strict

    # ==========================================================
    # GENERATE RECORD
    # ==========================================================

    def generate_record(self, record, mapping):

        if self._has_positions(mapping):

            total_length = self._get_record_length(mapping)

            output = [" "] * total_length

            for field_name, field_config in mapping.items():

                if not isinstance(field_config, dict):
                    continue

                # --------------------------------------------------
                # Fields without positions are ignored
                # --------------------------------------------------

                if "start" not in field_config:
                    continue

                start = field_config["start"]
                end = field_config["end"]

                expected_length = (
                    end - start + 1
                )

                configured_length = field_config.get(
                    "length",
                    expected_length,
                )

                # --------------------------------------------------
                # Validate configured length
                # --------------------------------------------------

                if configured_length != expected_length:

                    if self.strict:
                        raise ValueError(
                            f"Length mismatch for "
                            f"'{field_name}': "
                            f"start={start}, "
                            f"end={end}, "
                            f"calculated={expected_length}, "
                            f"configured={configured_length}"
                        )

                value = record.get(
                    field_name,
                    "",
                )

                value = self._format_value(
                    value=value,
                    config=field_config,
                    length=expected_length,
                    field_name=field_name,
                )

                output[
                    start - 1:end
                ] = value

            return "".join(output)

        # ------------------------------------------------------
        # Sequential mapping
        # ------------------------------------------------------

        return self._generate_sequential_record(
            record,
            mapping,
        )

    # ==========================================================
    # SEQUENTIAL RECORD
    # ==========================================================

    def _generate_sequential_record(
        self,
        record,
        mapping,
    ):
        """
        Generate records such as FHEAD where fields are defined
        using only their configured lengths.

        Fields are written in mapping declaration order.
        """

        output = []

        for field_name, field_config in mapping.items():

            if not isinstance(field_config, dict):
                continue

            # --------------------------------------------------
            # Fields without length
            # --------------------------------------------------

            if "length" not in field_config:

                if self.strict:
                    raise ValueError(
                        f"Missing length for "
                        f"'{field_name}'"
                    )

                continue

            length = field_config["length"]

            value = record.get(
                field_name,
                "",
            )

            value = self._format_value(
                value=value,
                config=field_config,
                length=length,
                field_name=field_name,
            )

            output.append(value)

        return "".join(output)

    # ==========================================================
    # CHECK POSITIONS
    # ==========================================================

    @staticmethod
    def _has_positions(mapping):

        for config in mapping.values():

            if (
                isinstance(config, dict)
                and "start" in config
                and "end" in config
            ):
                return True

        return False

    # ==========================================================
    # RECORD LENGTH
    # ==========================================================

    @staticmethod
    def _get_record_length(mapping):
        """
        Determine record length from maximum end position.
        """

        max_end = 0

        for config in mapping.values():

            if not isinstance(config, dict):
                continue

            if "end" in config:

                max_end = max(
                    max_end,
                    config["end"],
                )

        if max_end == 0:
            raise ValueError(
                "Mapping does not contain field positions."
            )

        return max_end

    # ==========================================================
    # FORMAT VALUE
    # ==========================================================

    def _format_value(
        self,
        value,
        config,
        length,
        field_name,
    ):
        """
        Convert value into exactly `length` characters.
        """

        # ------------------------------------------------------
        # Missing value = spaces
        # ------------------------------------------------------

        if value is None:
            value = ""

        value = str(value)

        # ------------------------------------------------------
        # ZERO-PADDED FIELDS
        # ------------------------------------------------------
        #
        # Used by fields such as:
        #
        # Line_ID
        # transaction_number
        #
        # Example:
        #     1 -> 0000000001
        #     2 -> 0000000002
        #
        # ------------------------------------------------------

        format_type = str(
            config.get("format", "")
        ).strip().upper()

        if format_type == "ZERO_PADDED":

            if value == "":
                return " " * length

            if not value.isdigit():

                raise ValueError(
                    f"Invalid zero-padded value "
                    f"for '{field_name}': {value}"
                )

            if len(value) > length:

                raise ValueError(
                    f"Value too long for "
                    f"'{field_name}': "
                    f"value='{value}', "
                    f"length={length}"
                )

            return value.zfill(length)

        # ------------------------------------------------------
        # Date / datetime
        # ------------------------------------------------------

        field_type = str(
            config.get("type", "")
        ).strip().upper()

        format_type = str(
            config.get("format", "")
        ).strip().upper()

        if field_type in {
            "DATETIME",
            "DATE",
            "TIMESTAMP",
        } or format_type == "YYYYMMDDHH24MISS":

            return self._format_datetime(
                value=value,
                config=config,
                length=length,
                field_name=field_name,
            )

        # ------------------------------------------------------
        # Numeric
        # ------------------------------------------------------

        if field_type in {
            "NUMBER",
            "NUMERIC",
            "NUMERIC_DECIMAL",
        }:

            return self._format_numeric(
                value=value,
                config=config,
                length=length,
                field_name=field_name,
            )

        # ------------------------------------------------------
        # Text
        # ------------------------------------------------------

        return self._format_text(
            value=value,
            length=length,
            field_name=field_name,
        )

    # ==========================================================
    # TEXT
    # ==========================================================

    def _format_text(
        self,
        value,
        length,
        field_name,
    ):
        """
        Text fields are left-aligned and space-padded.
        """

        # ------------------------------------------------------
        # Empty value
        # ------------------------------------------------------

        if value == "":
            return " " * length

        # ------------------------------------------------------
        # Validate length
        # ------------------------------------------------------

        if len(value) > length:

            if self.strict:

                raise ValueError(
                    f"Value too long for "
                    f"'{field_name}': "
                    f"value='{value}', "
                    f"length={length}"
                )

            value = value[:length]

        # ------------------------------------------------------
        # Left aligned
        # ------------------------------------------------------

        return value.ljust(length)

    # ==========================================================
    # DATE / DATETIME
    # ==========================================================

    def _format_datetime(
        self,
        value,
        config,
        length,
        field_name,
    ):
        """
        EDI dates are Char(14) in YYYYMMDDHH24MISS format.

        Date-only inputs are normalized to 00:00:00.

        Examples:
            20.05.2026 -> 20260520000000
            2026-05-20 -> 20260520000000
            20260520153045 -> 20260520153045
        """

        if value == "":
            return " " * length

        if length != 14:
            raise ValueError(
                f"Date field '{field_name}' must have length 14, "
                f"got {length}"
            )

        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            dt = datetime.combine(value, datetime.min.time())
        else:
            raw = str(value).strip()

            if raw == "":
                return " " * length

            # Already in required EDI format.
            if re.fullmatch(r"\d{14}", raw):
                try:
                    dt = datetime.strptime(raw, "%Y%m%d%H%M%S")
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid YYYYMMDDHH24MISS value for "
                        f"'{field_name}': {raw}"
                    ) from exc
            else:
                formats = (
                    "%d.%m.%Y",
                    "%d/%m/%Y",
                    "%d-%m-%Y",
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                    "%Y.%m.%d",
                    "%d.%m.%Y %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y%m%d",
                )

                dt = None
                for fmt in formats:
                    try:
                        dt = datetime.strptime(raw, fmt)
                        break
                    except ValueError:
                        continue

                if dt is None:
                    raise ValueError(
                        f"Invalid date value for '{field_name}': {raw}. "
                        "Expected YYYYMMDDHH24MISS or a supported "
                        "date input such as DD.MM.YYYY."
                    )

        output = dt.strftime("%Y%m%d%H%M%S")

        if len(output) != length:
            raise ValueError(
                f"Date value for '{field_name}' produced length "
                f"{len(output)}, expected {length}"
            )

        return output

    # ==========================================================
    # NUMERIC
    # ==========================================================

    def _format_numeric(
        self,
        value,
        config,
        length,
        field_name,
    ):
        """
        Numeric EDI fields are unsigned, right-aligned and zero-padded.

        For implied-decimal fields:
            Number(12,4):
                21585.490 -> 21585.4900
                          -> 215854900
                          -> 000215854900

        No decimal point is written into the EDI value.
        The sign belongs in its separate +/- field.
        """

        if value == "":
            return " " * length

        raw = str(value).strip()

        if raw == "":
            return " " * length

        # Numeric field itself must not contain a sign.
        if raw.startswith(("+", "-")):
            if raw.startswith("-"):
                raise ValueError(
                    f"Numeric field '{field_name}' received a signed value "
                    f"'{raw}'. The EDI sign must be stored in the separate "
                    "sign-indicator field."
                )
            raw = raw[1:].strip()

        decimal_places = config.get("decimal_places")

        if decimal_places is None:
            oracle_type = str(
                config.get("oracle_type", "")
            ).strip().upper()

            match = re.fullmatch(
                r"NUMBER\\s*\\(\\s*\\d+\\s*,\\s*(\\d+)\\s*\\)",
                oracle_type,
            )

            if match:
                decimal_places = int(match.group(1))

        if decimal_places is not None:
            try:
                decimal_places = int(decimal_places)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid decimal_places for '{field_name}': "
                    f"{decimal_places}"
                ) from exc

            if decimal_places < 0:
                raise ValueError(
                    f"decimal_places cannot be negative for '{field_name}'"
                )

            # Normalize common invoice formats:
            #   11,80 -> 11.80
            #   1.234,56 -> 1234.56
            if "," in raw:
                if "." in raw:
                    raw = raw.replace(".", "").replace(",", ".")
                else:
                    raw = raw.replace(",", ".")

            try:
                numeric_value = Decimal(raw)
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid numeric value for '{field_name}': {value}"
                ) from exc

            quantizer = Decimal(1).scaleb(-decimal_places)

            try:
                numeric_value = numeric_value.quantize(
                    quantizer,
                    rounding=ROUND_HALF_UP,
                )
            except InvalidOperation as exc:
                raise ValueError(
                    f"Invalid decimal precision for '{field_name}': {value}"
                ) from exc

            scaled_value = (
                numeric_value * (Decimal(10) ** decimal_places)
            ).to_integral_value(
                rounding=ROUND_HALF_UP
            )

            value = str(int(scaled_value))

        else:
            # Integer numeric field. Decimal values are not permitted.
            if "," in raw:
                if "." in raw:
                    raw = raw.replace(".", "").replace(",", ".")
                else:
                    raw = raw.replace(",", ".")

            try:
                numeric_value = Decimal(raw)
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid numeric value for '{field_name}': {value}"
                ) from exc

            if numeric_value != numeric_value.to_integral_value():
                raise ValueError(
                    f"Decimal value '{value}' is not valid for integer "
                    f"numeric field '{field_name}'"
                )

            value = str(
                int(numeric_value)
            )

        # EDI numeric value is unsigned; the sign is separate.
        if value.startswith(("+", "-")):
            raise ValueError(
                f"Formatted numeric value for '{field_name}' must be "
                f"unsigned: {value}"
            )

        # ------------------------------------------------------
        # Check length
        # ------------------------------------------------------

        if len(value) > length:
            raise ValueError(
                f"Numeric value too long for "
                f"'{field_name}': "
                f"value='{value}', "
                f"length={length}"
            )

        # ------------------------------------------------------
        # Zero padding
        # ------------------------------------------------------

        return value.zfill(length)

    # ==========================================================
    # VALIDATE RECORD
    # ==========================================================

    def validate_record(
        self,
        fixed_width_record,
        mapping,
    ):
        """
        Validate final fixed-width record.
        """

        if self._has_positions(mapping):

            expected_length = (
                self._get_record_length(mapping)
            )

        else:

            expected_length = sum(
                config.get("length", 0)
                for config in mapping.values()
                if isinstance(config, dict)
            )

        actual_length = len(
            fixed_width_record
        )

        if actual_length != expected_length:

            raise ValueError(
                f"Invalid record length. "
                f"Expected={expected_length}, "
                f"Actual={actual_length}"
            )

        return True