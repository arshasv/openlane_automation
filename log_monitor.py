import time
import json
import asyncio
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import aio_pika

# RabbitMQ configuration
RABBITMQ_HOST = "localhost"
RABBITMQ_QUEUE = "openlane_notifications"

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
    def __init__(self, rabbitmq_connection, loop):
        self.rabbitmq_connection = rabbitmq_connection
        self.loop = loop  # Pass the asyncio event loop

    def on_created(self, event):
        # Check if the created file is in the target list
        if not event.is_directory:
            filename = event.src_path.split("/")[-1]
            if filename in TARGET_FILES:
                print(f"File created: {filename}")
                # Schedule the coroutine in the dedicated event loop thread
                asyncio.run_coroutine_threadsafe(self.publish_to_rabbitmq(filename), self.loop)

    async def publish_to_rabbitmq(self, filename):
        """
        Publish a message to RabbitMQ when a target file is created.
        """
        print(f"DEBUG: Publishing message for file: {filename}")
        try:
            channel = await self.rabbitmq_connection.channel()
            message_body = {
                "event": "file_created",
                "filename": filename,
                "status": "success",
                "message": f"{filename} has been created."
            }
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(message_body).encode()),
                routing_key=RABBITMQ_QUEUE,
            )
            print(f"DEBUG: Published message to RabbitMQ: {message_body}")
        except Exception as e:
            print(f"ERROR: Failed to publish message to RabbitMQ: {e}")

async def connect_to_rabbitmq():
    """
    Establish a connection to RabbitMQ.
    """
    try:
        connection_string = f"amqp://guest:guest@{RABBITMQ_HOST}/"
        return await aio_pika.connect_robust(connection_string)
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {e}")
        raise

def monitor_directory(path_to_watch, rabbitmq_connection, loop):
    event_handler = FileCreationHandler(rabbitmq_connection, loop)
    observer = Observer()
    # Set recursive=True to monitor subfolders
    observer.schedule(event_handler, path=path_to_watch, recursive=True)
    observer.start()
    print(f"Monitoring directory and subfolders: {path_to_watch}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def start_event_loop_in_thread():
    """
    Start the asyncio event loop in a dedicated thread.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    thread = Thread(target=loop.run_forever, daemon=True)
    thread.start()
    return loop

if __name__ == "__main__":
    # Replace with the directory you want to monitor
    directory_to_watch = "/home/opentrends/CHIPIFY/openlane2/designs"
    
    # Start the asyncio event loop in a dedicated thread
    loop = start_event_loop_in_thread()
    
    # Connect to RabbitMQ
    rabbitmq_connection = asyncio.run_coroutine_threadsafe(connect_to_rabbitmq(), loop).result()
    
    # Start monitoring the directory
    monitor_directory(directory_to_watch, rabbitmq_connection, loop)
