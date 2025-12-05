from natKit.codegen.api import schema_pb2
from natKit.api import CsvStream


class SchemaBuilder:
    @staticmethod
    def build_from_proto_message(message: bytes):
        stream_schema = schema_pb2.StreamSchema()
        stream_schema.ParseFromString(message)
        if stream_schema.type == schema_pb2.SchemaType.CSV:
            return CsvStream.create_from_proto_schema(stream_schema)
        return CsvStream.create_from_proto_message(self.number_of_channels, message)

    def build_schema_proto_message(self) -> schema_pb2.StreamSchema:
        stream_schema = schema_pb2.StreamSchema()
        stream_schema.name = self.name
        stream_schema.channels = self.number_of_channels
        stream_schema.type = schema_pb2.SchemaType.CSV
