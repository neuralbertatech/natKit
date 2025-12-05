from confluent_kafka import Consumer
from confluent_kafka import Producer

from natKit.common.kafka import TopicName
from natKit.common.util import Fifo

from threading import Thread

from time import sleep

from typing import Callable
from typing import NoReturn


class TopicConnection(Thread):
    def __init__(
        self,
        topic_name: TopicName,
        consumer: Consumer,
        producer: Producer,
        message_callback: Callable[[bytes], NoReturn],
    ):
        super().__init__()

        self.topic_name = topic_name
        self.consumer = consumer
        self.producer = producer
        self.message_callback = message_callback
        self.consumer.subscribe([self.topic_name.topic_string])
        self._do_read_data = True

        self.start()

    @staticmethod
    def create_from_config(
        topic_name: TopicName,
        consumer_config: dict,
        producer_config: dict,
        message_callback: Callable[[bytes], NoReturn],
    ):
        return TopicConnection(
            topic_name,
            Consumer(consumer_config),
            Producer(producer_config),
            message_callback,
        )

    def run(self):
        while True:
            self._read()
            if not self._do_read_data:
                break
            sleep(0.001)
        self.producer.flush()

    def stop(self):
        self._do_read_data = False

    def _read(self):
        message = self.consumer.poll(timeout=1.0)
        if message is None:
            return
        elif message.error():
            # TODO: Add error logging here
            print(message.error())
        else:
            self.message_callback(message.value())

    def write(self, data: bytes) -> NoReturn:
        self.producer.produce(self.topic_name.topic_string, data)
