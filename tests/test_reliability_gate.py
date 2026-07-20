import urllib.error
from unittest.mock import MagicMock, patch

from deployment import reliability_gate


def test_reliability_gate_honors_retry_after_on_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(reliability_gate, "REQUEST_INTERVAL_SECONDS", 0)
    rate_limited = urllib.error.HTTPError(
        "https://demo.example/v1/intentions",
        429,
        "Too Many Requests",
        {"Retry-After": "7"},
        None,
    )
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"items": []}'

    with (
        patch.object(
            reliability_gate.urllib.request,
            "urlopen",
            side_effect=[rate_limited, response],
        ) as urlopen,
        patch.object(reliability_gate.time, "sleep") as sleep,
    ):
        result = reliability_gate.request(
            "https://demo.example",
            "/v1/intentions",
            rate_limit_retries=1,
        )

    assert result == {"items": []}
    assert urlopen.call_count == 2
    sleep.assert_called_once_with(7)


def test_reliability_gate_does_not_retry_other_http_errors(monkeypatch) -> None:
    monkeypatch.setattr(reliability_gate, "REQUEST_INTERVAL_SECONDS", 0)
    unavailable = urllib.error.HTTPError(
        "https://demo.example/v1/intentions",
        503,
        "Service Unavailable",
        {},
        None,
    )

    with patch.object(
        reliability_gate.urllib.request,
        "urlopen",
        side_effect=unavailable,
    ) as urlopen:
        try:
            reliability_gate.request("https://demo.example", "/v1/intentions")
        except urllib.error.HTTPError as error:
            assert error.code == 503
        else:
            raise AssertionError("Expected the original HTTP 503 error")

    assert urlopen.call_count == 1
