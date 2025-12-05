import unittest

from natKit.common.kafka import Encoding
from natKit.common.kafka import TopicConnection
from natKit.common.kafka import TopicName
from natKit.common.kafka import TopicType

from numpy.testing import assert_array_equal

from time import sleep

from typing import NoReturn

from unittest.mock import Mock


class TestTopicName(unittest.TestCase):
    def test_topic_name__to_str(self) -> NoReturn:
        topic_name = TopicName(id=10, type=TopicType.DATA, encoder_name="MyEncoder", schema_name="MySchema")
        expected = 'Topic: [id: 10, type: TopicType.DATA, topic_string: "data-10-MyEncoder-MySchema", encoder_name: "MyEncoder", schema_name: "MySchema"]'
        self.assertEqual(expected, str(topic_name))

    def test_topic_name__to_str__with_topic_string(self) -> NoReturn:
        topic_name = TopicName(10, TopicType.DATA, encoder_name="MyEncoder", schema_name="MySchema", topic_string="foobar-42-MyEncoder-MySchema")
        expected = 'Topic: [id: 10, type: TopicType.DATA, topic_string: "foobar-42-MyEncoder-MySchema", encoder_name: "MyEncoder", schema_name: "MySchema"]'
        self.assertEqual(expected, str(topic_name))

    def test_topic_name__parse_from_topic_string__data(self) -> NoReturn:
        topic_string = "data-10-MyEncoder-MySchema"
        topic_name = TopicName.parse_from_topic_string(topic_string)
        expected = TopicName(10, TopicType.DATA, encoder_name="MyEncoder", schema_name="MySchema")
        self.assertEqual(expected, topic_name)

    def test_topic_name__parse_from_topic_string__meta(self) -> NoReturn:
        topic_string = "meta-123-MyEncoder-MySchema"
        topic_name = TopicName.parse_from_topic_string(topic_string)
        expected = TopicName(123, TopicType.META, encoder_name="MyEncoder", schema_name="MySchema")
        self.assertEqual(expected, topic_name)

    def test_topic_name__parse_from_topic_string__data_with_encoding(self) -> NoReturn:
        topic_string = "data-10-MyEncoder-MySchema"
        topic_name = TopicName.parse_from_topic_string(topic_string)
        expected = TopicName(10, TopicType.DATA, encoder_name="MyEncoder", schema_name="MySchema")
        self.assertEqual(expected, topic_name)

    def test_topic_name__topic_name_to_topic_string__data(self) -> NoReturn:
        topic_name = TopicName(10, TopicType.DATA, encoder_name="MyEncoder", schema_name="MySchema")
        topic_string = TopicName.topic_name_to_topic_string(topic_name)
        expected = "data-10-MyEncoder-MySchema"
        self.assertEqual(expected, topic_string)

    def test_topic_name__topic_name_to_topic_string__meta(self) -> NoReturn:
        topic_name = TopicName(123, TopicType.META, encoder_name="MyEncoder", schema_name="MySchema")
        topic_string = TopicName.topic_name_to_topic_string(topic_name)
        expected = "meta-123-MyEncoder-MySchema"
        self.assertEqual(expected, topic_string)

    def test_topic_name__topic_name_with_topic_name(self) -> NoReturn:
        topic_name = TopicName(123, TopicType.META, encoder_name="MyEncoder", schema_name="MySchema", topic_string="hi-10-there-world")
        expected = "hi-10-there-world"
        self.assertEqual(expected, topic_name.topic_string)


if __name__ == "__main__":
    unittest.main()
