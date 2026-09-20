from .resolver import MappingResolver


class RecordMapper:

    def __init__(self, resolver: MappingResolver):
        self.resolver = resolver

    def map_record(self, mapping):
        """
        Map one record using its mapping dictionary.
        """

        record = {}

        for field_name, field_config in mapping.items():

            value = self.resolver.resolve(
                field_name,
                field_config
            )

            record[field_name] = value

        return record

    def map_fhead(self, mapping):
        return self.map_record(mapping)

    def map_thead(self, mapping):
        return self.map_record(mapping)

    def map_tdetl(self, mapping):
        return self.map_record(mapping)

    def map_tvats(self, mapping):
        return self.map_record(mapping)

    def map_ttail(self, mapping):
        return self.map_record(mapping)

    def map_ftail(self, mapping):
        return self.map_record(mapping)