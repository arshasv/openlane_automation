# import time
# import json
# import asyncio
# import logging
# from threading import Thread
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# import aio_pika

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,  # Set to DEBUG for more detailed logs
#     format="%(asctime)s - %(levelname)s - %(message)s"
# )

# # RabbitMQ configuration
# RABBITMQ_HOST = "rabbitmq"
# RABBITMQ_QUEUE = "verilog_queue"

# # List of target filenames to monitor
# TARGET_FILES = {
#     "yosys-synthesis.log",
#     "openroad-floorplan.log",
#     "openroad-detailedplacement",
#     "openroad-cts.log",
#     "openroad-detailedrouting.log",
#     "magic-spiceextraction.log",
#     "netgen-lvs.log"
# }

# class FileCreationHandler(FileSystemEventHandler):
#     def __init__(self, rabbitmq_connection, loop):
#         self.rabbitmq_connection = rabbitmq_connection
#         self.loop = loop  # Pass the asyncio event loop

#     def on_created(self, event):
#         # Check if the created file is in the target list
#         if not event.is_directory:
#             filename = event.src_path.split("/")[-1]
#             if filename in TARGET_FILES:
#                 logging.info(f"File created: {filename}")
#                 # Schedule the coroutine in the dedicated event loop thread
#                 asyncio.run_coroutine_threadsafe(self.publish_to_rabbitmq(filename), self.loop)

#     async def publish_to_rabbitmq(self, filename):
#         """
#         Publish a message to RabbitMQ when a target file is created.
#         """
#         logging.debug(f"Publishing message for file: {filename}")
#         try:
#             channel = await self.rabbitmq_connection.channel()
#             message_body = {
#                 "event": "file_created",
#                 "filename": filename,
#                 "status": "success",
#                 "message": f"{filename} has been created."
#             }
#             await channel.default_exchange.publish(
#                 aio_pika.Message(body=json.dumps(message_body).encode()),
#                 routing_key=RABBITMQ_QUEUE,
#             )
#             logging.info(f"Published message to RabbitMQ: {message_body}")
#         except Exception as e:
#             logging.error(f"Failed to publish message to RabbitMQ: {e}")

# async def connect_to_rabbitmq():
#     """
#     Establish a connection to RabbitMQ.
#     """
#     try:
#         connection_string = f"amqp://guest:guest@{RABBITMQ_HOST}/"
#         logging.info(f"Connecting to RabbitMQ at {connection_string}")
#         return await aio_pika.connect_robust(connection_string)
#     except Exception as e:
#         logging.error(f"Failed to connect to RabbitMQ: {e}")
#         raise

# def monitor_directory(path_to_watch, rabbitmq_connection, loop):
#     event_handler = FileCreationHandler(rabbitmq_connection, loop)
#     observer = Observer()
#     observer.schedule(event_handler, path=path_to_watch, recursive=True)
#     observer.start()
#     logging.info(f"Monitoring directory and subfolders: {path_to_watch}")
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         observer.stop()
#         logging.info("Stopped monitoring directory.")
#     finally:
#         loop.run_until_complete(rabbitmq_connection.close())
#         logging.info("RabbitMQ connection closed.")
#     observer.join()

# def start_event_loop_in_thread():
#     """
#     Start the asyncio event loop in a dedicated thread.
#     """
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     thread = Thread(target=loop.run_forever, daemon=True)
#     thread.start()
#     logging.info("Asyncio event loop started in a dedicated thread.")
#     return loop

# if __name__ == "__main__":
#     # Replace with the directory you want to monitor
#     directory_to_watch = "/app/openlane2"
    
#     # Start the asyncio event loop in a dedicated thread
#     loop = start_event_loop_in_thread()
    
#     # Connect to RabbitMQ
#     try:
#         rabbitmq_connection = asyncio.run_coroutine_threadsafe(connect_to_rabbitmq(), loop).result()
#         logging.info("Connected to RabbitMQ successfully.")
#     except Exception as e:
#         logging.error(f"Failed to connect to RabbitMQ: {e}")
#         exit(1)
    
#     # Start monitoring the directory
#     monitor_directory(directory_to_watch, rabbitmq_connection, loop)


import time
import json
import asyncio
import logging
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ✅ Import shared RabbitMQ async publisher
from rabbitmq_utils import publish_message_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# List of target filenames to monitor
TARGET_FILES = {
    "yosys-synthesis.log",
    "openroad-floorplan.log",
    "openroad-detailedplacement",
    "openroad-cts.log",
    "openroad-detailedrouting.log",
    "magic-spiceextraction.log",
    "netgen-lvs.log"
}

class FileCreationHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop

    def on_created(self, event):
        if not event.is_directory:
            filename = event.src_path.split("/")[-1]
            if filename in TARGET_FILES:
                logging.info(f"File created: {filename}")
                message = {
                    "event": "file_created",
                    "filename": filename,
                    "status": "success",
                    "message": f"{filename} has been created."
                }
                asyncio.run_coroutine_threadsafe(publish_message_async(message), self.loop)

def monitor_directory(path_to_watch, loop):
    event_handler = FileCreationHandler(loop)
    observer = Observer()
    observer.schedule(event_handler, path=path_to_watch, recursive=True)
    observer.start()
    logging.info(f"Monitoring directory and subfolders: {path_to_watch}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Stopped monitoring directory.")
    observer.join()

def start_event_loop_in_thread():
    """
    Start the asyncio event loop in a dedicated thread.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    thread = Thread(target=loop.run_forever, daemon=True)
    thread.start()
    logging.info("Asyncio event loop started in a dedicated thread.")
    return loop

if __name__ == "__main__":
    # The path to monitor
    directory_to_watch = "/app/openlane2"

    # Start asyncio loop in background thread
    loop = start_event_loop_in_thread()

    # Start monitoring directory
    monitor_directory(directory_to_watch, loop)
