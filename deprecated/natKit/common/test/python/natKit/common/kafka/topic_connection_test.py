import unittest

from natKit.common.kafka import Encoding
from natKit.common.kafka import TopicConnection
from natKit.common.kafka import TopicName
from natKit.common.kafka import TopicType

from typing import NoReturn

from unittest.mock import Mock


class Value:
    def __init__(self):
        self.val = None

    def set(self, val):
        self.val = val


class TestTopicConnection(unittest.TestCase):
    def setUp(self) -> NoReturn:
        self.DATA_TOPIC_NAME = TopicName(10, TopicType.DATA, encoder_name="MyEncoder", schema_name="MySchema")
        self.BINARY_DATA = b"hello" 
        message = Mock()
        message.value = Mock(return_value=self.BINARY_DATA)
        message.error = Mock(return_value=None)
        self.mock_consumer = Mock()
        self.mock_consumer.poll = Mock(return_value=message)
        self.mock_producer = Mock()

    def test_topic__read(self) -> NoReturn:
        read_message = Value()
        self.topic = TopicConnection(self.DATA_TOPIC_NAME, self.mock_consumer, self.mock_producer, lambda m : read_message.set(m))
        self.topic.stop()
        self.topic.join()
        self.mock_consumer.poll.assert_called()
        self.assertEqual(self.BINARY_DATA, read_message.val)

    def test_topic__write(self) -> NoReturn:
        self.topic = TopicConnection(self.DATA_TOPIC_NAME, self.mock_consumer, self.mock_producer, lambda m : None)
        self.topic.write(self.BINARY_DATA)
        self.topic.stop()
        self.topic.join()
        self.mock_producer.produce.assert_called_with(self.DATA_TOPIC_NAME.topic_string, self.BINARY_DATA)


if __name__ == "__main__":
    unittest.main()
