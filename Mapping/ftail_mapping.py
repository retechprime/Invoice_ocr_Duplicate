PREDEFINED_FIELDS = {
    "ftail": {
        "record_descriptor": {
            "field_name": "Record Descriptor",
            "source": "PREDEFINED",
            "type": "CONSTANT",
            "value": "FTAIL",
            "start": 1,
            "end": 5,
            "length": 5,
            "required": True,
        },
        "line_id": {
            "field_name": "Line ID",
            "source": "SEQUENCE",
            "type": "FILE_SEQUENCE",
            "start": 6,
            "end": 15,
            "length": 10,
            "format": "ZERO_PADDED",
            "required": True,
        },
        "number_of_lines": {
            "field_name": "Number of Lines",
            "source": "CALCULATED",
            "type": "NUMERIC",
            "start": 16,
            "end": 25,
            "length": 10,
            "required": True,
            "calculation": "COUNT_FILE_LINES_EXCLUDING_FHEAD_FTAIL",
        },
    }
}
