#!/usr/bin/env python3


class KafkaManagerHelper:
    @staticmethod
    def get_default_producer_configuration() -> dict:
        return {
            "bootstrap.servers": self.broker,
            "queue.buffering.max.ms": 5,
        }

    @staticmethod
    def get_default_consumer_configuration() -> dict:
        return {
            "bootstrap.servers": self.broker,
            "group.id": str(random.randint(0, 2**64)),
            "session.timeout.ms": 6000,
            "auto.offset.reset": "earliest",
            "enable.auto.offset.store": False,
            # "fetch.wait.max.ms": 5,
        }
