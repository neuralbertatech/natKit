from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
import os
import threading

import websockets
from websockets.asyncio.server import ServerConnection

from natvr.kafka_transport import open_stream_consumer
from natvr.models import HandStateV1
from natvr.topics import hand_state


LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    kafka_broker: str = os.getenv("NATVR_KAFKA_BROKER", "127.0.0.1:29092")
    kafka_group_id: str = os.getenv(
        "NATVR_KAFKA_GROUP_ID", "natvr-hand-state-bridge"
    )
    kafka_topic: str = os.getenv("NATVR_HAND_STATE_TOPIC", hand_state("demo"))
    kafka_direct_assign: bool = os.getenv("NATVR_KAFKA_DIRECT_ASSIGN", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    kafka_partition: int = int(os.getenv("NATVR_KAFKA_PARTITION", "0"))
    ws_host: str = os.getenv("NATVR_WS_HOST", "0.0.0.0")
    ws_port: int = int(os.getenv("NATVR_WS_PORT", "8765"))


class ClientHub:
    def __init__(self) -> None:
        self._clients: set[ServerConnection] = set()
        self._lock = asyncio.Lock()

    async def add(self, websocket: ServerConnection) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def remove(self, websocket: ServerConnection) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, payload: dict[str, object]) -> None:
        message = json.dumps(payload, separators=(",", ":"))
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            return
        results = await asyncio.gather(
            *(client.send(message) for client in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results, strict=True):
            if isinstance(result, Exception):
                LOG.warning("dropping websocket client after send failure: %s", result)
                await self.remove(client)
                await client.close()


def _consumer_loop(
    config: BridgeConfig,
    queue: asyncio.Queue[dict[str, object]],
    loop: asyncio.AbstractEventLoop,
    stop_event: threading.Event,
) -> None:
    consumer, _ = open_stream_consumer(
        bootstrap_servers=config.kafka_broker,
        group_id=config.kafka_group_id,
        topics=[config.kafka_topic],
        auto_offset_reset="latest",
        direct_assign=config.kafka_direct_assign,
        partition=config.kafka_partition,
    )
    try:
        while not stop_event.is_set():
            msg = consumer.poll(0.5)
            if msg is None:
                continue
            error = msg.error()
            if error is not None:
                LOG.error("kafka consume error: %s", error)
                continue
            try:
                state = HandStateV1.from_json_bytes(msg.value())
            except Exception as exc:
                LOG.error("invalid hand.state payload on %s: %s", config.kafka_topic, exc)
                continue
            loop.call_soon_threadsafe(queue.put_nowait, state.to_bridge_dict())
    finally:
        consumer.close()


async def _fanout_loop(queue: asyncio.Queue[dict[str, object]], hub: ClientHub) -> None:
    while True:
        payload = await queue.get()
        await hub.broadcast(payload)


async def _client_handler(websocket: ServerConnection, hub: ClientHub) -> None:
    await hub.add(websocket)
    try:
        await websocket.send(
            json.dumps(
                {
                    "type": "status",
                    "message": "connected",
                },
                separators=(",", ":"),
            )
        )
        async for _ in websocket:
            pass
    finally:
        await hub.remove(websocket)


async def run_bridge(config: BridgeConfig) -> None:
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    hub = ClientHub()
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_consumer_loop,
        args=(config, queue, loop, stop_event),
        daemon=True,
        name="natvr-kafka-consumer",
    )
    thread.start()
    fanout_task = asyncio.create_task(_fanout_loop(queue, hub))
    try:
        async with websockets.serve(
            lambda websocket: _client_handler(websocket, hub),
            config.ws_host,
            config.ws_port,
        ):
            LOG.info(
                "hand-state bridge listening on ws://%s:%d from topic %s via %s",
                config.ws_host,
                config.ws_port,
                config.kafka_topic,
                config.kafka_broker,
            )
            await asyncio.Future()
    finally:
        stop_event.set()
        await asyncio.to_thread(thread.join, 2.0)
        fanout_task.cancel()
        try:
            await fanout_task
        except asyncio.CancelledError:
            pass


def main() -> None:
    logging.basicConfig(
        level=os.getenv("NATVR_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_bridge(BridgeConfig()))


if __name__ == "__main__":
    main()
