## 2026-10-08 - [Use of assert for validation]
**Vulnerability:** Found `assert bbox is not None` used for validation in `src/snake_arena/record/gif.py`. If python runs in optimized mode (e.g., `python -O`), assertions are skipped, meaning `bbox` could be `None` leading to downstream errors or insecure states.
**Learning:** This codebase uses assertions for runtime validation which can be bypassed in optimized environments.
**Prevention:** Always use explicit `if` statements and raise specific exceptions instead of `assert` when validating data that may be critical for logic control.
