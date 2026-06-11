import json
import logging
from datetime import datetime, timezone
import pika
from app.core.config import Settings
from app.services.rabbitmq_topology import SYNC_EXCHANGE, declare_sync_topology

logger = logging.getLogger(__name__)

def publish_sync_job(settings: Settings, job_type: str, store_id: int, payload: dict) -> None:
    """
    Publishes a SyncJob to RabbitMQ using pika.
    """
    params = pika.URLParameters(settings.effective_rabbitmq_url)
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        declare_sync_topology(channel)
        
        job_id = f"{job_type}-{int(datetime.now(timezone.utc).timestamp())}"
        payload_job_id = payload.get("job_id")
        sync_job = {
            "id": job_id,
            "type": job_type,
            "store_id": store_id,
            "payload": payload,
            "idempotency_key": f"{job_type}:{payload_job_id}" if payload_job_id is not None else job_id,
            "attempt": 0,
            "requested_at": datetime.now(timezone.utc).isoformat()
        }
        
        body = json.dumps(sync_job)
        channel.basic_publish(
            exchange=SYNC_EXCHANGE,
            routing_key=job_type,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type="application/json",
            )
        )
        logger.info(f"Published job {job_id} to RabbitMQ exchange wb.sync with routing key {job_type}")
    finally:
        connection.close()
