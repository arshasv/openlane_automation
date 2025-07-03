import os
import json
import logging
import asyncio
import aio_pika
from dotenv import load_dotenv

# Load .env for environment variables if running locally
load_dotenv()

# Read RabbitMQ config from env
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "verilog_queue")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

# Async publisher (can be used in FastAPI or monitoring scripts)
async def publish_message_async(message: dict):
    try:
        logging.info(f"[rabbitmq_utils] Publishing message: {message}")
        connection = await aio_pika.connect_robust(
            f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
        )
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(RABBITMQ_QUEUE, durable=True)

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=RABBITMQ_QUEUE
            )
            logging.info("[rabbitmq_utils] Message published successfully.")
    except Exception as e:
        logging.error(f"[rabbitmq_utils] Failed to publish message: {str(e)}")

# Safe sync wrapper for FastAPI (can call from normal functions)
def publish_message(message: dict):
    try:
        asyncio.run(publish_message_async(message))
    except RuntimeError as e:
        logging.warning(f"[rabbitmq_utils] RuntimeError: {str(e)} — using existing event loop")
        loop = asyncio.get_event_loop()
        loop.create_task(publish_message_async(message))
