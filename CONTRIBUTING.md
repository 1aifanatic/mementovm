# Contributing

1. Open an issue describing the proposed behavior and its safety impact.
2. Keep domain logic deterministic where possible; models may suggest but must
   not bypass validators or policy.
3. Add tests for state transitions, duplicate delivery, and failure behavior.
4. Run `make lint`, `make test`, and `make build` before opening a pull request.
5. Never commit API keys, customer data, or private replay bundles.

By contributing, you agree that your contribution is licensed under Apache-2.0.

