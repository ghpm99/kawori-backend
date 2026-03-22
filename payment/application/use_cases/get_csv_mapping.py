from payment.utils import csv_header_mapping


class GetCSVMappingUseCase:
    def execute(self, csv_headers):
        return [
            {"csv_column": column, "system_field": csv_header_mapping(column)}
            for column in csv_headers
        ]
