from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..domain.program import build_demo_program
from ..llm.qwen_gateway import QwenGateway
from .validator import intention_schema, validate_program


class CompilerService:
    def __init__(self, settings: Settings, gateway: QwenGateway | None = None):
        self.settings = settings
        self.gateway = gateway or QwenGateway(settings)

    async def compile(
        self,
        *,
        content: str,
        intent_id: str,
        message_id: str,
        session_id: str,
        user_id: str,
        timezone_name: str,
    ) -> dict[str, Any]:
        if not self.settings.qwen_configured:
            return self._fallback(content, intent_id, message_id, session_id, user_id)
        reference_time = datetime.now(timezone.utc)
        try:
            candidate, metadata = await self.gateway.compile_intention(
                content=content,
                schema=intention_schema(),
                reference_time=reference_time.isoformat(),
                timezone=timezone_name,
                known_entities={
                    "contract_id": "contract-043",
                    "deal_id": "deal-043",
                    "document_version": "v7",
                    "recipient": "Dana",
                    "escalation_contact": "Mark",
                },
            )
            candidate = self._bind_server_fields(
                candidate, intent_id, message_id, session_id, user_id, content, metadata
            )
            errors = validate_program(candidate)
            if errors:
                repaired, repair_meta = await self.gateway.repair_intention(
                    candidate=candidate, errors=errors, schema=intention_schema()
                )
                candidate = self._bind_server_fields(
                    repaired, intent_id, message_id, session_id, user_id, content, repair_meta
                )
                candidate.setdefault("model_metadata", {})["repair_attempted"] = True
            return candidate
        except Exception as error:
            fallback = self._fallback(content, intent_id, message_id, session_id, user_id)
            fallback["model_metadata"]["fallback_reason"] = type(error).__name__
            return fallback

    def _fallback(
        self, content: str, intent_id: str, message_id: str, session_id: str, user_id: str
    ) -> dict:
        program = build_demo_program(
            intent_id=intent_id,
            version=1,
            message_id=message_id,
            session_id=session_id,
            source_text=content,
            model="deterministic-demo-compiler",
            request_id="fallback-no-cloud-call",
        )
        program["user_id"] = user_id
        return program

    @staticmethod
    def _bind_server_fields(
        candidate: dict,
        intent_id: str,
        message_id: str,
        session_id: str,
        user_id: str,
        content: str,
        metadata: dict,
    ) -> dict:
        candidate["schema_version"] = "1.0.0"
        candidate["intent_id"] = intent_id
        candidate["version"] = 1
        candidate["user_id"] = user_id
        candidate["status"] = "DORMANT"
        candidate.setdefault("source", {}).update(
            {
                "message_id": message_id,
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "original_quote": content,
                "parent_version": None,
            }
        )
        candidate.setdefault("assumptions", [])
        candidate.setdefault("unresolved_fields", [])
        candidate["model_metadata"] = {
            "provider": "Qwen Cloud",
            "model": metadata.get("model", "unknown"),
            "prompt_version": "intent-compiler-v1",
            "request_id": metadata.get("request_id", "unknown"),
            "usage": metadata.get("usage", {}),
        }
        return candidate
