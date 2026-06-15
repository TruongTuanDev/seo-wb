from pika.adapters.blocking_connection import BlockingChannel


SYNC_EXCHANGE = "wb.sync"
SYNC_QUEUE = "wb.sync.jobs"
SYNC_DEAD_LETTER_EXCHANGE = "wb.sync.dlx"
SYNC_DEAD_LETTER_QUEUE = "wb.sync.jobs.dead"
SYNC_ROUTING_KEYS = ("card.push", "product.sync", "finance.sync")


def declare_sync_topology(channel: BlockingChannel) -> None:
    channel.exchange_declare(exchange=SYNC_EXCHANGE, exchange_type="direct", durable=True)
    channel.exchange_declare(exchange=SYNC_DEAD_LETTER_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(
        queue=SYNC_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": SYNC_DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": "failed",
        },
    )
    channel.queue_declare(queue=SYNC_DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(exchange=SYNC_DEAD_LETTER_EXCHANGE, queue=SYNC_DEAD_LETTER_QUEUE, routing_key="failed")
    for routing_key in SYNC_ROUTING_KEYS:
        channel.queue_bind(exchange=SYNC_EXCHANGE, queue=SYNC_QUEUE, routing_key=routing_key)
