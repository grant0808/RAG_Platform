import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from foundry.api.dependencies import get_container
from foundry.core.container import Container
from foundry.schemas.cag import CacheCreateRequest, CacheEntryResponse
from foundry.services.orchestrator import CacheEntry

router = APIRouter(prefix="/cag", tags=["cag"])


@router.get("/cache", response_model=list[CacheEntryResponse])
async def list_cache(
    container: Container = Depends(get_container),
) -> list[CacheEntryResponse]:
    now_mono = time.monotonic()
    results = []

    for key, entry in list(container.orchestrator.cache.items()):
        ttl = entry.expires_at - now_mono
        if ttl > 0:
            exp_time = datetime.fromtimestamp(datetime.now().timestamp() + ttl, UTC)
            results.append(
                CacheEntryResponse(
                    key=key,
                    answer=entry.answer,
                    expires_at_timestamp=entry.expires_at,
                    expires_at=exp_time,
                    ttl_seconds_remaining=round(ttl, 1),
                )
            )
    return results


@router.post(
    "/cache",
    response_model=CacheEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cache(
    payload: CacheCreateRequest,
    container: Container = Depends(get_container),
) -> CacheEntryResponse:
    orchestrator = container.orchestrator
    orchestrator.cache[payload.key] = CacheEntry(
        answer=payload.answer, expires_at=time.monotonic() + payload.ttl_seconds
    )

    exp_time = datetime.fromtimestamp(datetime.now().timestamp() + payload.ttl_seconds, UTC)

    return CacheEntryResponse(
        key=payload.key,
        answer=payload.answer,
        expires_at_timestamp=time.monotonic() + payload.ttl_seconds,
        expires_at=exp_time,
        ttl_seconds_remaining=float(payload.ttl_seconds),
    )


@router.delete("/cache/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cache(key: str, container: Container = Depends(get_container)):
    orchestrator = container.orchestrator
    if key in orchestrator.cache:
        del orchestrator.cache[key]
        return
    raise HTTPException(status_code=404, detail="Cache entry not found")
