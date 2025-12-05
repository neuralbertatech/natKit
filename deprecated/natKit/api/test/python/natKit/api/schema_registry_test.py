#from natKit.api import Encoding
#from natKit.api import Schema
#from natKit.api import SchemaRegistry

#from typing import NoReturn

#from unittest import TestCase
#from unittest.mock import Mock


#class SchemaRegistryTest(TestCase):
#    def setUp(self):
#        self.mock_serializer = Mock()
#        self.mock_deserializer = Mock()
#        self.schema_foo_json = Schema("foo", Encoding.JSON, self.mock_serializer, self.mock_deserializer, '{name: "thing"}')
#        self.schema_bar_avro = Schema("bar", Encoding.AVRO, self.mock_serializer, self.mock_deserializer, '{title: "sir"}')
#        self.schema_bar_proto = Schema("bar", Encoding.PROTOBUF, self.mock_serializer, self.mock_deserializer,  '{value: [1, 2, 3]}')
#        self.registry = SchemaRegistry([self.schema_foo_json, self.schema_bar_avro, self.schema_bar_proto])

#    def test_query(self) -> NoReturn:
#        schema = self.registry.query("bar", Encoding.AVRO)
#        self.assertEqual(self.schema_bar_avro, schema)

#    def test_registry(self):
#        new_schema = Schema("new", Encoding.RAW, self.mock_serializer, self.mock_deserializer, "skdfjsdls")
#        self.registry.register(new_schema)
#        queried_value = self.registry.query("new", Encoding.RAW)
#        self.assertEqual(new_schema, queried_value)
