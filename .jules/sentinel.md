## 2026-10-03 - [Missing Input Length Limits (DoS risk)]
**Vulnerability:** The application lacks upper bounds on input arguments like `--size`, `--food`, and `--cell`. This allows a user to provide maliciously large numbers (e.g. `--size 100000000`), which causes the application to allocate massive grids, resulting in an Out-of-Memory crash or hanging indefinitely.
**Learning:** Argument parsers must not only ensure the correct data type or a minimum value, but also a reasonable maximum bound to prevent resource exhaustion attacks. Furthermore, uncaught exceptions bubble up as stack traces, exposing internal implementation details.
**Prevention:** Implement rigorous boundary checking (both min and max limits) for all user-provided integers in CLI arguments and employ a global try-except block to gracefully handle unexpected application errors without leaking stack traces.
## 2024-05-18 - Missing CLI input length limits and leaked stack traces

**Vulnerability:** The CLI did not place bounds on properties like `--size` or `--food`, which permitted the application to allocate extremely large grids when requested, exposing it to memory exhaustion Denial of Service (DoS) attacks. Furthermore, unhandled exceptions were leaking full stack traces to the output, thereby exposing internal application architecture.
**Learning:** `argparse` types can be mapped to customized validator functions to check limits rather than just parsing raw primitive types. Missing boundary constraints on arguments that trigger memory allocation lead directly to a vulnerability.
**Prevention:** Bound variables that determine the size of allocated structures to safe upper limits using argument parsing. Wrap entry points with generic exception handlers to prevent raw exception leakage to users.
