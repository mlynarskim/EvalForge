from redis import Redis
from rq import Queue, Worker

from app.config import settings


def run() -> None:
    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue("experiments", connection=connection)], connection=connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    run()
