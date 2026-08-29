import os
import asyncio
import hashlib
import logging
import redis
from groq import Groq

logger = logging.getLogger(__name__)
CACHE_VERSION = os.getenv("CACHE_VERSION", "v1") 


client = Groq(api_key=os.getenv("GROQ_API_KEY"))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

redis_client = None
try:
    redis_client = redis.Redis(
        host=REDIS_HOST, port=6379, db=0,
        decode_responses=True, socket_connect_timeout=2, retry_on_timeout=False
    )
    redis_client.ping()
    logger.info(f"Redis connected at {REDIS_HOST}.")
except Exception as e:
    logger.warning(f"Redis failed: {e}. Degraded mode.")
    redis_client = None

async def get_llm_response(prompt: str, system_prompt: str, secret: str) -> str:
    CACHE_VERSION = os.getenv("CACHE_VERSION", "v1")
    cache_key = hashlib.md5(f"{CACHE_VERSION}:{prompt}".encode()).hexdigest()

    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached: return cached
        except Exception as e:
            logger.error(f"Cache read fail: {e}")

    try:
        loop = asyncio.get_running_loop()
        completion = await loop.run_in_executor(None, lambda: client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="openai/gpt-oss-120b", 
            temperature=0.7,           
            max_tokens=500             
        ))
        reply = completion.choices[0].message.content.strip()
        logger.debug(f"RAW_LLM: '{reply}'")

        if redis_client:
            try: redis_client.setex(cache_key, 3600, reply)
            except Exception as e: logger.error(f"Cache write fail: {e}")
        return reply
    except Exception as e:
        logger.error(f"LLM Error [{type(e).__name__}]: {e}")
        return f"Service Error: {str(e)}"