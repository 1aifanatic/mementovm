# Devpost draft - Latch: Prospective Memory for Agents

> Submission operator: replace the three `TODO` values after Alibaba Cloud and
> YouTube publication, then remove this note before pasting into Devpost.

## Track

Track 1 - MemoryAgent

## Subtitle

Powered by MementoVM, an executable intention compiler and event-indexed memory
runtime built for Qwen Cloud.

## Short description

Most agents remember what happened. Latch remembers what must happen,
recognizes the correct future cue or missing event, adapts when plans change,
and executes approved actions exactly once.

## Inspiration

Long-term memory for agents is usually evaluated as retrieval: can the system
recall a fact, preference, or old conversation when asked? Real assistants also
need prospective memory: the ability to retain a future intention while other
work continues, notice when a time, event, state change, or non-event makes it
relevant, and act without being prompted again.

That behavior is difficult. A useful agent must avoid both missed obligations
and false alarms. It must handle updates such as "actually, wait for finance
approval too," cancellation in a later session, stale conditions such as a
closed deal or changed document version, quiet-hour preferences, and duplicate
events. It must also know when a completed obligation should leave active
memory. We built Latch to make that lifecycle explicit, safe, and measurable.

## What it does

Latch converts conversational commitments into immutable, versioned Intention
Programs. Each program contains an allowlisted action, typed triggers,
inhibitors, a validity envelope, optional absence rules, monitoring hints,
approval policy, forgetting policy, and provenance back to the user's words.

The reference workflow coordinates a contract approval. A later-session update
adds finance approval to the original legal cue. Similar but incorrect events
are rejected with visible evidence. Matching legal and finance events make the
program due, a remembered focus block defers the interruption, and a human
approval authorizes exactly one simulated draft. Duplicate webhook and approval
replays cannot create a second action. A separate 48-hour absence rule drafts an
escalation, after which completed cues leave hot memory while audit evidence is
preserved.

The UI includes a Memory Debugger, immutable version history, event timeline,
ten-step deterministic simulator, approval inspector, system proof panel, and a
reproducible evaluation dashboard.

## How we built it

All model traffic crosses one Qwen adapter. `qwen3.7-plus` compiles natural
language into structured JSON and receives at most one repair attempt.
`qwen3.6-flash` is reserved for bounded semantic cue adjudication and concise
explanations. Exact identifiers, lifecycle state, inhibitors, approval policy,
and action claiming remain deterministic. When credentials or quota are
unavailable, the public scenario switches to a clearly labeled deterministic
compiler so judging remains reproducible.

The frontend is Next.js and the API is FastAPI. PostgreSQL with pgvector stores
immutable program versions, cue indexes, events, decisions, approvals, actions,
jobs, and evaluation runs. A PostgreSQL-backed worker monitors time and absence.
External writes require an action-bound approval with expiry. A unique
idempotency key and atomic database claim provide exactly-once execution under
retries.

The production profile runs Caddy, Next.js, FastAPI, the worker, and PostgreSQL
as Docker Compose services on Alibaba Cloud ECS. The application uses the
official Alibaba Cloud OSS SDK to upload private replay bundles and benchmark
evidence.

## Challenges

The hardest problem was balancing recall and restraint. Monitoring every
related phrase catches more cues but creates false alarms; being too
conservative misses obligations. We separated exact channel, event, entity,
validity, and inhibitor checks from optional semantic adjudication.

Update safety was equally important. Mutating memory in place makes it hard to
know which instruction authorized an action. Latch creates immutable complete
versions, invalidates pending work from older versions, and binds approval to a
canonical action hash.

Finally, reliable future behavior must survive duplicate events and worker
retries. Database-backed transitions, event IDs, atomic action claims, and
idempotency keys make those failures observable and safe.

## Accomplishments

- Typed prospective-memory programs compiled from ordinary instructions.
- Event, compound, inhibitor, validity, time, and absence triggers.
- Cross-session revision with immutable version history.
- A debugger that explains both action and non-action.
- Human approval and exactly-once simulated tool execution.
- Purpose-based forgetting from the active context path.
- A 60-case benchmark and automated ten-run reliability gate.
- A public Apache-2.0 repository with CI, security checks, deck, and demo cut.

## What we learned

Agent memory is not only retrieval. Reliable future behavior requires state,
policy, time, event routing, version history, and lifecycle management.
Untrusted external text must never redefine an action or policy stored from the
user. Qwen is most effective inside a constrained architecture: structured
compilation at write time and bounded semantic judgment at event time, with
deterministic validation around every model call.

## What's next

Production Gmail, Outlook, Slack, calendar, and contract-system connectors;
team memory with purpose-bound access; richer stale-memory propagation;
recurring prospective intentions; and hosted SDKs for other agent frameworks.

## Built with

Qwen Cloud, qwen3.7-plus, qwen3.6-flash, Alibaba Cloud ECS, Alibaba Cloud OSS,
FastAPI, Python, Pydantic, PostgreSQL, pgvector, SQLAlchemy, Alembic, Next.js,
React, TypeScript, Docker, GitHub Actions, Pytest, pip-audit, and npm audit.

## Links

- Live application: `TODO_ALIBABA_LIVE_URL`
- Public repository: https://github.com/1aifanatic/mementovm
- Public YouTube demo: `TODO_YOUTUBE_URL`
- Local 2:37 demo cut: https://github.com/1aifanatic/mementovm/blob/main/docs/demo/Latch-MementoVM-Demo.mp4
- Architecture: https://github.com/1aifanatic/mementovm/blob/main/docs/architecture/system.mmd
- Alibaba Cloud proof: https://github.com/1aifanatic/mementovm/blob/main/deployment/ALIBABA_CLOUD_PROOF.md
- Alibaba OSS integration: https://github.com/1aifanatic/mementovm/blob/main/backend/app/integrations/alibaba_oss.py
- Pitch deck: https://github.com/1aifanatic/mementovm/blob/main/docs/pitch/Latch-MementoVM-Pitch-Deck.pdf
- Deployment evidence: `TODO_ALIBABA_EVIDENCE_URL`

## Testing instructions

1. Open `TODO_ALIBABA_LIVE_URL`. No account is required.
2. Open Simulator and choose **Reset**.
3. Run **Contract Approval - Official Demo** one step at a time, or use
   **Auto-play** for the complete flow.
4. Watch exact rejection evidence, focus-time deferral, the action hash,
   approval, duplicate suppression, absence detection, and cue forgetting.
5. Open Active Memory for immutable versions, Evaluation for the reproducible
   baseline comparison, and System for Qwen routes and cloud proof.

## Measured results

- Dataset: PM-Mini v1, 60 original deterministic scenarios.
- MementoVM prospective-memory F1: 1.000.
- Vector-memory F1: 0.500.
- Todo-ledger F1: 0.615.
- False alarms: 0.
- Misses: 0.
- Duplicate actions: 0.
- Full judge-scenario reliability runs: 10/10 passed.
- Submitted commit: `TODO_SUBMISSION_COMMIT`.
