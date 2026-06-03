from fastapi import APIRouter

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/health")
def ai_health():
    return {
        "status": "ok",
        "feature": "ai_reports_v1_infra",
    }
