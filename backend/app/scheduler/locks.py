"""Per-user Redis lock so concurrent runs for the same user never overlap (§14).

A user may have several profiles; the lock is on the *user* so two profiles don't hammer
the same provider accounts (and the same rate limits) at once.

Acquire is ``SET key token NX EX ttl``. Release is a compare-and-delete Lua script so a
run that overran its TTL can never delete a lock that now belongs to someone else.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis

from app.core.config import get_settings

LOCK_TTL_SECONDS = 30 * 60

# Delete only if we still hold the token — otherwise leave the current owner's lock alone.
_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class UserLockBusy(Exception):
    """Another run for this user is already in flight."""


def lock_key(user_id: int) -> str:
    return f"ajh:lock:user:{user_id}"


@asynccontextmanager
async def user_lock(user_id: int, ttl: int = LOCK_TTL_SECONDS) -> AsyncIterator[None]:
    client: redis.Redis = redis.from_url(get_settings().redis_url)
    key = lock_key(user_id)
    token = uuid.uuid4().hex
    try:
        acquired = await client.set(key, token, nx=True, ex=ttl)
        if not acquired:
            raise UserLockBusy(f"a pipeline run is already active for user {user_id}")
        try:
            yield
        finally:
            await client.eval(_RELEASE_SCRIPT, 1, key, token)
    finally:
        await client.aclose()
