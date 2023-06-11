#from natKit.api import Encoding
#from natKit.api import Schema
#
#from typing import List
#from typing import NoReturn
#from typing import Optional
#
#
#def read_schema(path):
#    with open(path, 'r') as f:
#        return f.read()
#
#
#class SchemaRegistry:
#    def __init__(self, schemas: List[Schema] = []) -> NoReturn:
#        self.schemas = schemas
#
#    def register(self, schema: Schema) -> NoReturn:
#        self.schemas.append(schema)
#
#    def query(self, name: str, encoding: Encoding) -> Optional[Schema]:
#        for schema in self.schemas:
#            if schema.name == name and schema.encoding == encoding:
#                return schema
#
#        return None

from __future__ import annotations

from .schema import Schema
from .basic_meta_info_schema import BasicMetaInfoSchema
from .simple_message_schema import SimpleMessageSchema

from typing import NoReturn
from typing import Optional


class SchemaRegistry:
    def __init__(self) -> NoReturn:
        self.registered_schemas = {}

    def register(self, schema: Schema, schema_name: Optional[str] = None) -> NoReturn:
        if schema_name is None:
            schema_name = schema.get_name()
        self.registered_schemas[schema_name] = schema

    def lookup(self, schema_name: str) -> Optional[Schema]:
        if schema_name in self.registered_schemas:
            return self.registered_schemas[schema_name]
        else:
            return None

    @staticmethod
    def register_defaults(registry: SchemaRegistry) -> SchemaRegistry:
        registry.register(SimpleMessageSchema)
        registry.register(BasicMetaInfoSchema)
        return registry

    @staticmethod
    def create() -> SchemaRegistry:
        registry = SchemaRegistry()
        return SchemaRegistry.register_defaults(registry)
