import unittest

from natKit.common.kafka import KafkaManager
from natKit.common.kafka import TopicName
from natKit.common.kafka import TopicType

from numpy.testing import assert_array_equal

from time import sleep

from typing import NoReturn

from unittest.mock import Mock


class MockClusterMetadata:
    def __init__(self, topics):
        self.topics = topics


class KafkaManagerTest(unittest.TestCase):
    def setUp(self):
        self.topic1_name = "DATA-00000000001"
        self.topic1_data = []
        self.mock_admin_client = Mock()
        self.mock_admin_client.list_topics = Mock(return_value=MockClusterMetadata({self.topic1_name: self.topic1_data}))
        self.manager = KafkaManager("", "", "", self.mock_admin_client)

    def test_query_topic_names(self):
        queried_topics = self.manager.query_topic_names()
        self.assertEqual([self.topic1_name], queried_topics)
