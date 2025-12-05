from natkit.common.kafka import Stream
from natkit.common.kafka import TopicName
from natkit.common.kafka import KafkaManager

from threading import Thread

from time import time
from time import sleep

from typing import NoReturn
from typing import Optional


class StreamWatcher(Thread):
    def __init__(self, name: TopicName, kafka_manager: KafkaManager):
        self.topic_name = name
        self._kafka_manager = _kafka_manager
        self.has_stream_been_found = False
        self._should_continue_search = True
        self._polling_rate = 1.0  # 1 second

        self.start()

    def run(self) -> NoReturn:
        self._search()

    def get_topic_name(self) -> Optional[TopicName]:
        if self.has_stream_been_found:
            return self.topic_name
        else:
            return None

    def stop(self) -> NoReturn:
        self._should_continue_search = False

    def _search(self):
        while self.should_continue_search:
            start_time = time()

            topic_names = self._kafka_manager.query_topic_names()
            for name in topic_names:
                if name.topic_string == self.topic_name.topic_string:
                    self.topic_name = name
                    self.has_stream_been_found = True
                    self._should_continue_search = False
                    break

            end_time = time()
            time_diff = end_time - start_time
            if time_diff < self._polling_rate:
                sleep(self._polling_rate - time_diff)
