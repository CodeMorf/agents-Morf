import asyncio
import logging

from redis.asyncio import Redis

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agents-morf-worker")


async def main():
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    while True:
        try:
            item = await redis.blpop("agents_morf:jobs", timeout=5)
            if item:
                _, payload = item
                logger.info("Received job: %s", payload[:500])
        except Exception:
            logger.exception("Worker loop failed")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
