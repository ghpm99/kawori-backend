def csv_header_mapping(header_column):
    mapping = {
        "data": "date",
        "valor": "value",
        "amount": "amount",
        "identificador": "ignore",
        "descrição": "description",
        "date": "date",
        "title": "description",
        "amount": "value",
    }
    normalized_header = header_column.strip().lower()
    return mapping.get(normalized_header, "ignore")
