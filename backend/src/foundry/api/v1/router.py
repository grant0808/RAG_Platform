from fastapi import APIRouter

from foundry.api.v1.endpoints import (
    cag,
    chat,
    deployments,
    evaluation,
    health,
    pipelines,
    providers,
    public,
    sources,
)

router = APIRouter()

router.include_router(health.router)
router.include_router(providers.router)
router.include_router(sources.router)
router.include_router(pipelines.router)
router.include_router(chat.router)
router.include_router(deployments.router)
router.include_router(public.router)
router.include_router(cag.router)
router.include_router(evaluation.router)
