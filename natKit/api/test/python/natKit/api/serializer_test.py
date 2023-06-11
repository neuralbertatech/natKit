from natKit.api import Encoding
from natKit.api import Schema
from natKit.api import SchemaRegistry
from natKit.api import Serializer

from typing import NoReturn

from unittest import TestCase
from unittest.mock import Mock


class JsonTestSchema:
    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def createFromDict(obj: dict, ctx=None):
        return JsonTestSchema(obj["name"])

    @staticmethod
    def toDict(schema, ctx=None):
        return {"name": schema.name}


class SerializerTest(TestCase):
    def setUp(self):
        self.json_schema = """
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "JsonTestSchema",
  "description": "A test structure",
  "type": "object",
  "properties": {
    "name": {
      "description": "A name",
      "type": "string"
    },
  },
  "required": [ "name" ]
}
        """
        self.registry_client = Mock()

    #def test_serialize(self) -> NoReturn:
    #    serializer = Serializer(Encoding.JSON, self.json_schema, self.registry_client, JsonTestSchema.toDict)
    #    data = JsonTestSchema("hello")
    #    serialized_data = serializer.serialize(data)
    #    expected = b"{name=\"hello\"}"
    #    self.assertEqual(expected, serialized_data)
