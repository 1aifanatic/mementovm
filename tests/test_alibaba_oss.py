from unittest.mock import Mock, patch

from backend.app.config import Settings
from backend.app.integrations.alibaba_oss import AlibabaOSS


def test_oss_configuration_accepts_ecs_ram_role_without_access_keys() -> None:
    settings = Settings(
        alibaba_cloud_ecs_ram_role="mementovm-oss-role",
        alibaba_cloud_oss_region="ap-southeast-1",
        alibaba_cloud_oss_endpoint="https://oss-ap-southeast-1.aliyuncs.com",
        alibaba_cloud_oss_bucket="mementovm-proof",
    )

    assert settings.oss_configured is True


def test_oss_configuration_requires_region_with_v4_auth() -> None:
    settings = Settings(
        alibaba_cloud_ecs_ram_role="mementovm-oss-role",
        alibaba_cloud_oss_endpoint="https://oss-ap-southeast-1.aliyuncs.com",
        alibaba_cloud_oss_bucket="mementovm-proof",
    )

    assert settings.oss_configured is False


@patch("backend.app.integrations.alibaba_oss.oss2.Bucket")
@patch("backend.app.integrations.alibaba_oss.oss2.ProviderAuthV4")
@patch("backend.app.integrations.alibaba_oss.EcsRamRoleCredentialsProvider")
def test_ecs_ram_role_uses_metadata_credentials_and_signature_v4(
    provider: Mock,
    provider_auth_v4: Mock,
    bucket: Mock,
) -> None:
    settings = Settings(
        alibaba_cloud_ecs_ram_role="mementovm role",
        alibaba_cloud_oss_region="ap-southeast-1",
        alibaba_cloud_oss_endpoint="https://oss-ap-southeast-1.aliyuncs.com",
        alibaba_cloud_oss_bucket="mementovm-proof",
    )

    AlibabaOSS(settings)._bucket()

    provider.assert_called_once_with(
        "http://100.100.100.200/latest/meta-data/ram/security-credentials/"
        "mementovm%20role"
    )
    provider_auth_v4.assert_called_once_with(provider.return_value)
    bucket.assert_called_once_with(
        provider_auth_v4.return_value,
        settings.alibaba_cloud_oss_endpoint,
        settings.alibaba_cloud_oss_bucket,
        region=settings.alibaba_cloud_oss_region,
    )


def test_access_key_fallback_also_uses_signature_v4() -> None:
    settings = Settings(
        alibaba_cloud_access_key_id="test-id",
        alibaba_cloud_access_key_secret="test-secret",
        alibaba_cloud_oss_region="ap-southeast-1",
        alibaba_cloud_oss_endpoint="https://oss-ap-southeast-1.aliyuncs.com",
        alibaba_cloud_oss_bucket="mementovm-proof",
    )

    with (
        patch("backend.app.integrations.alibaba_oss.oss2.Bucket") as bucket,
        patch("backend.app.integrations.alibaba_oss.oss2.ProviderAuthV4") as provider_auth_v4,
        patch("backend.app.integrations.alibaba_oss.StaticCredentialsProvider") as provider,
    ):
        AlibabaOSS(settings)._bucket()

    provider.assert_called_once_with("test-id", "test-secret")
    provider_auth_v4.assert_called_once_with(provider.return_value)
    bucket.assert_called_once_with(
        provider_auth_v4.return_value,
        settings.alibaba_cloud_oss_endpoint,
        settings.alibaba_cloud_oss_bucket,
        region=settings.alibaba_cloud_oss_region,
    )
