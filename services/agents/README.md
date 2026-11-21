# joby-agents

Python agent service. One codebase, two processes:

- `agents-api`: FastAPI, internal only. Validates requests from Nest, enqueues runs, returns `202`.
- `agents-worker`: claims runs from `agents.run_queue` with `SKIP LOCKED` and executes LangGraph graphs.

See the root README for setup and `docs/ARCHITECTURE.md` §3.3 for the design.
