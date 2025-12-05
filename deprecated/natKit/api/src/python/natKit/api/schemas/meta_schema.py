from typing import NoReturn


class MetaSchema:
    def __init__(self, name: str, data_schema: str):
        self.name = name
        self.data_schema = data_schema

    @staticmethod
    def createFromDict(obj: dict, ctx=None):
        return MetaSchema(obj["name"], obj["data_schema"])

    @staticmethod
    def toDict(schema, ctx=None):
        return {"name": schema.name, "data_schema": schema.data_schema}

    def __str__(self):
        return 'MetaSchema: {{"name": {}, "data_schema": {}}}'.format(self.name, self.data_schema)
