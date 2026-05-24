def forward(schema, column):
    if column not in schema["columns"]:
        schema["columns"].append(column)
    return schema


def rollback(schema, column):
    return schema
