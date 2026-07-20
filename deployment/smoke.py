import argparse
import json
import urllib.request


def request(base: str, path: str, method: str = "GET") -> dict:
    req = urllib.request.Request(f"{base.rstrip('/')}{path}", method=method)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    health = request(args.base_url, "/healthz")
    ready = request(args.base_url, "/readyz")
    intentions = request(args.base_url, "/v1/intentions")
    assert health["status"] == "ok"
    assert ready["status"] in {"ready", "degraded"}
    assert intentions["items"], "Demo intention was not seeded"
    print(json.dumps({"health": health, "ready": ready, "intentions": len(intentions["items"])}, indent=2))


if __name__ == "__main__":
    main()

