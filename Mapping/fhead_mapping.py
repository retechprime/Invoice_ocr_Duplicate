PREDEFINED_FIELDS = {
    "fhead": {
        "record_descriptor": {"value": "FHEAD", "length": 5},
        "Line_id": {
            "type": "SEQUENTIAL",
            "length": 10,
            "start_value": 1,
            "format": "zero_padded",
        },
        "Gentran ID": {"value": "UPINV", "length": 5},
        "File_Date": {"type": "SYSTEM_DATE", "length": 14, "format": "%Y%m%d%H%M%S"},
    },
}
