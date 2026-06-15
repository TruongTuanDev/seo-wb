import asyncio
import json
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties
from redis import Redis

import app.models  # noqa: F401
from app.core.config import get_settings
from app.services.rabbitmq_topology import SYNC_QUEUE, declare_sync_topology
from app.services.wb_sync_job_processor import InvalidSyncJobError, RetryableSyncJobError, WbSyncJobProcessor


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
thread_state = threading.local()


def _event_loop() -> asyncio.AbstractEventLoop:
    loop = getattr(thread_state, "event_loop", None)
    if loop is None:
        loop = asyncio.new_event_loop()
        thread_state.event_loop = loop
    return loop


def _process_message(processor: WbSyncJobProcessor, body: bytes) -> str:
    try:
        job = json.loads(body)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidSyncJobError("RabbitMQ sync message is not valid JSON.") from exc
    if not isinstance(job, dict):
        raise InvalidSyncJobError("RabbitMQ sync message must be a JSON object.")
    return _event_loop().run_until_complete(processor.process(job))


class WbSyncWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        redis_url = self.settings.effective_redis_url
        if not redis_url:
            raise RuntimeError("Redis is required by the WB sync worker.")
        self.processor = WbSyncJobProcessor(self.settings, Redis.from_url(redis_url, decode_responses=True))
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wb-sync-job")

    def run(self) -> None:
        while True:
            try:
                self._consume()
            except KeyboardInterrupt:
                return
            except Exception:
                logger.exception("WB sync worker connection failed; retrying in 5 seconds.")
                time.sleep(5)

    def _consume(self) -> None:
        connection = pika.BlockingConnection(pika.URLParameters(self.settings.effective_rabbitmq_url))
        try:
            channel = connection.channel()
            declare_sync_topology(channel)
            channel.basic_qos(prefetch_count=self.settings.rabbitmq_prefetch_count)
            channel.basic_consume(queue=SYNC_QUEUE, on_message_callback=self._on_message)
            logger.info("WB sync worker started. queue=%s", SYNC_QUEUE)
            channel.start_consuming()
        finally:
            if connection.is_open:
                connection.close()

    def _on_message(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ) -> None:
        future = self.executor.submit(_process_message, self.processor, body)
        future.add_done_callback(
            lambda completed: channel.connection.add_callback_threadsafe(
                lambda: self._finish_message(channel, method, completed)
            )
        )

    @staticmethod
    def _finish_message(channel: BlockingChannel, method: Basic.Deliver, future: Future[str]) -> None:
        if not channel.is_open:
            return
        exc = future.exception()
        if exc is None:
            logger.info("WB sync message handled. routing_key=%s result=%s", method.routing_key, future.result())
            channel.basic_ack(method.delivery_tag)
        elif isinstance(exc, RetryableSyncJobError):
            logger.warning("Retryable WB sync error; requeueing. error=%s", exc)
            channel.basic_nack(method.delivery_tag, requeue=True)
        else:
            logger.error("WB sync message failed; dead-lettering. error=%s", exc)
            channel.basic_nack(method.delivery_tag, requeue=False)


def main() -> None:
    WbSyncWorker().run()


if __name__ == "__main__":
    main()
