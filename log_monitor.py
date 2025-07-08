
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
    "openroad-detailedplacement.log",
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
