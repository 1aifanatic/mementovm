"""Alibaba Cloud OSS proof integration for replay and benchmark exports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import oss2
from oss2.credentials import EcsRamRoleCredentialsProvider, StaticCredentialsProvider

from ..config import Settings


class AlibabaOSS:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.oss_configured

    def _bucket(self) -> oss2.Bucket:
        if not self.configured:
            raise RuntimeError("Alibaba Cloud OSS is not configured")

        if self.settings.alibaba_cloud_ecs_ram_role:
            role_name = quote(self.settings.alibaba_cloud_ecs_ram_role, safe="")
            metadata_url = (
                "http://100.100.100.200/latest/meta-data/ram/security-credentials/"
                f"{role_name}"
            )
            credentials = EcsRamRoleCredentialsProvider(metadata_url)
        else:
            credentials = StaticCredentialsProvider(
                self.settings.alibaba_cloud_access_key_id,
                self.settings.alibaba_cloud_access_key_secret,
            )

        # Signature V1 is unavailable for new OSS buckets. ProviderAuthV4 works
        # with both temporary ECS-role credentials and least-privilege RAM keys.
        auth = oss2.ProviderAuthV4(credentials)
        return oss2.Bucket(
            auth,
            self.settings.alibaba_cloud_oss_endpoint,
            self.settings.alibaba_cloud_oss_bucket,
            region=self.settings.alibaba_cloud_oss_region,
        )

    def upload_replay(self, run_id: str, replay: dict[str, Any]) -> dict[str, Any]:
        key = f"{self.settings.alibaba_cloud_oss_prefix}/{run_id}.json"
        body = json.dumps(replay, indent=2, default=str).encode("utf-8")
        result = self._bucket().put_object(key, body, headers={"Content-Type": "application/json"})
        return {
            "provider": "Alibaba Cloud OSS",
            "bucket": self.settings.alibaba_cloud_oss_bucket,
            "region": self.settings.alibaba_cloud_oss_region,
            "object_key": key,
            "etag": result.etag,
            "request_id": result.request_id,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

    def healthcheck(self) -> bool:
        if not self.configured:
            return False
        self._bucket().get_bucket_info()
        return True
