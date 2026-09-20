from Mapping_Engine.resolver import MappingResolver
from Mapping_Engine.record_mapper import RecordMapper
from Mapping_Engine.fixed_width_generator import FixedWidthGenerator

from Mapping.fhead_mapping import PREDEFINED_FIELDS as FHEAD_MAPPING
from Mapping.thead_mapping import PREDEFINED_FIELDS as THEAD_MAPPING
from Mapping.tdetl_mapping import PREDEFINED_FIELDS as TDETL_MAPPING
from Mapping.tvats_mapping import PREDEFINED_FIELDS as TVATS_MAPPING
from Mapping.ttail_mapping import PREDEFINED_FIELDS as TTAIL_MAPPING
from Mapping.ftail_mapping import PREDEFINED_FIELDS as FTAIL_MAPPING


class EDIMappingService:

    def __init__(self):
        self.generator = FixedWidthGenerator(strict=True)

    # MAIN EDI GENERATION


    def generate_edi(
        self,
        ocr_data: dict,
        web_service_data: dict,
    ):
        ocr_data = ocr_data or {}
        web_service_data = web_service_data or {}

        records = []

        # ------------------------------------------------------
        # GLOBAL SEQUENCE
        # ------------------------------------------------------

        file_sequence = 1
        transaction_number = 1

        # ------------------------------------------------------
        # CHILD COLLECTIONS
        # ------------------------------------------------------

        line_items = (
            ocr_data.get("line_items")
            or ocr_data.get("lines")
            or []
        )

        # VAT is optional.
        # If VAT is not present, this remains an empty list
        # and no TVATS records will be generated.
        vat_lines = (
            ocr_data.get("vat_lines")
            or []
        )

        # FHEAD

        fhead_mapping = FHEAD_MAPPING.get(
            "fhead",
            FHEAD_MAPPING
        )

        fhead_resolver = MappingResolver(
            ocr_data=ocr_data,
            web_service_data=web_service_data,
            file_sequence=file_sequence,
            transaction_number=transaction_number,
        )

        fhead_mapper = RecordMapper(
            fhead_resolver
        )

        fhead = fhead_mapper.map_record(
            fhead_mapping
        )

        fhead_record = self.generator.generate_record(
            fhead,
            fhead_mapping
        )

        self.generator.validate_record(
            fhead_record,
            fhead_mapping
        )

        records.append(fhead_record)

        # Continue global sequence
        file_sequence = fhead_resolver.file_sequence

        # THEAD

        thead_mapping = THEAD_MAPPING.get(
            "thead",
            THEAD_MAPPING
        )

        thead_resolver = MappingResolver(
            ocr_data=ocr_data,
            web_service_data=web_service_data,
            file_sequence=file_sequence,
            transaction_number=transaction_number,
        )

        thead_mapper = RecordMapper(
            thead_resolver
        )

        thead = thead_mapper.map_record(
            thead_mapping
        )

        thead_record = self.generator.generate_record(
            thead,
            thead_mapping
        )

        self.generator.validate_record(
            thead_record,
            thead_mapping
        )

        records.append(thead_record)

        # Continue global sequence
        file_sequence = thead_resolver.file_sequence


        # TDETL

        tdetl_mapping = TDETL_MAPPING.get(
            "tdetl",
            TDETL_MAPPING
        )

        for line_item in line_items:

            # --------------------------------------------------
            # OCR data for current line
            # --------------------------------------------------

            line_ocr_data = {
                **ocr_data,
                **line_item,
                "current_line": line_item,
            }

            # --------------------------------------------------
            # Web Service data for current line
            #
            # Expected structure:
            #
            # line_item = {
            #     ...,
            #     "web_service_data": {
            #         ...
            #     }
            # }
            #
            # Global web_service_data remains available as a
            # fallback.
            # --------------------------------------------------

            line_web_service_data = {
                **web_service_data,
                **line_item.get("web_service_data", {}),
                "current_line": line_item,
            }

            line_resolver = MappingResolver(
                ocr_data=line_ocr_data,
                web_service_data=line_web_service_data,
                file_sequence=file_sequence,
                transaction_number=transaction_number,
            )

            line_mapper = RecordMapper(
                line_resolver
            )

            tdetl = line_mapper.map_record(
                tdetl_mapping
            )

            tdetl_record = self.generator.generate_record(
                tdetl,
                tdetl_mapping
            )

            self.generator.validate_record(
                tdetl_record,
                tdetl_mapping
            )

            records.append(tdetl_record)

            # Continue global sequence
            file_sequence = line_resolver.file_sequence

        # ======================================================
        # TVATS
        # ======================================================

        tvats_mapping = TVATS_MAPPING.get(
            "tvats",
            TVATS_MAPPING
        )
        vat_lines_to_process = vat_lines if vat_lines else [{}]


        for vat_line in vat_lines_to_process:

            # --------------------------------------------------
            # Web Service data for current VAT line
            # --------------------------------------------------

            vat_web_service_data = {
                **web_service_data,
                **(
                    vat_line.get("web_service_data", {})
                    if isinstance(vat_line, dict)
                    else {}
                ),
                "current_vat": vat_line,
            }

            vat_resolver = MappingResolver(
                ocr_data=ocr_data,
                web_service_data=vat_web_service_data,
                file_sequence=file_sequence,
                transaction_number=transaction_number,
            )

            vat_mapper = RecordMapper(
                vat_resolver
            )

            tvats = vat_mapper.map_record(
                tvats_mapping
            )

            tvats_record = self.generator.generate_record(
                tvats,
                tvats_mapping
            )

            self.generator.validate_record(
                tvats_record,
                tvats_mapping
            )

            records.append(tvats_record)

            # Continue global sequence
            file_sequence = vat_resolver.file_sequence

        # ======================================================
        # TTAIL
        # ======================================================

        ttail_mapping = TTAIL_MAPPING.get(
            "ttail",
            TTAIL_MAPPING
        )

        ttail_resolver = MappingResolver(
            ocr_data=ocr_data,
            web_service_data=web_service_data,
            file_sequence=file_sequence,
            transaction_number=transaction_number,
            calculation_context={
                "detail_lines": line_items,
            },
        )

        ttail_mapper = RecordMapper(
            ttail_resolver
        )

        ttail = ttail_mapper.map_record(
            ttail_mapping
        )

        ttail_record = self.generator.generate_record(
            ttail,
            ttail_mapping
        )

        self.generator.validate_record(
            ttail_record,
            ttail_mapping
        )

        records.append(ttail_record)

        # Continue global sequence
        file_sequence = ttail_resolver.file_sequence

        # FTAIL

        ftail_mapping = FTAIL_MAPPING.get(
            "ftail",
            FTAIL_MAPPING
        )

        transaction_line_count = max(
            len(records) - 1,
            0
        )

        ftail_resolver = MappingResolver(
            ocr_data=ocr_data,
            web_service_data=web_service_data,
            file_sequence=file_sequence,
            transaction_number=transaction_number,
            calculation_context={
                "transaction_lines": transaction_line_count,
            },
        )

        ftail_mapper = RecordMapper(
            ftail_resolver
        )

        ftail = ftail_mapper.map_record(
            ftail_mapping
        )

        ftail_record = self.generator.generate_record(
            ftail,
            ftail_mapping
        )

        self.generator.validate_record(
            ftail_record,
            ftail_mapping
        )

        records.append(ftail_record)

        # ======================================================
        # FINAL EDI
        # ======================================================

        edi_text = "\n".join(records)

        return {
            "status": "generated",
            "format": "EDI801",
            "record_count": len(records),
            "fixed_width_records": records,
            "edi_text": edi_text,
        }