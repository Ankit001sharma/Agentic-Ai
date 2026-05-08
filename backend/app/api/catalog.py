"""Read-only catalog endpoints (tools.yaml, risk.yaml, model config)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_api_key
from app.core.config import get_settings

router = APIRouter()

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(name: str) -> Any:
    s = get_settings()
    if name == "tools":
        rel = getattr(s, "tools_yaml_path", "tools.yaml") or "tools.yaml"
    elif name == "risk":
        rel = getattr(s, "risk_yaml_path", "risk.yaml") or "risk.yaml"
    else:
        raise ValueError(name)
    path = _BACKEND_ROOT / rel
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{rel} not found")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.get("/tools")
async def tools_yaml(_: str = Depends(require_api_key)) -> Any:
    return _load_yaml("tools")


@router.get("/risk")
async def risk_yaml(_: str = Depends(require_api_key)) -> Any:
    return _load_yaml("risk")


@router.get("/models")
async def models_config(_: str = Depends(require_api_key)) -> dict[str, Any]:
    s = get_settings()
    return {
        "vllm_base_url_configured": bool(s.vllm_base_url),
        "vllm_judge_model": s.vllm_judge_model,
        "nemotron_model": s.nemotron_model,
        "mistral_model": s.mistral_model,
        "mistral_model": s.mistral_model if s.mistral_api_key else None,
        "default_model": s.default_model,
        "allow_cloud_fallback": s.allow_cloud_fallback,
        "risk_allow_max": s.risk_allow_max,
        "risk_mask_max": s.risk_mask_max,
        "risk_escalate_max": s.risk_escalate_max,
    }
