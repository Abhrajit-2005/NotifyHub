import logging
from worker.notification_worker import NotificationWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    worker = NotificationWorker()
    worker.start()
