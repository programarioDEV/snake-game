## 2024-05-18 - Missing CLI input length limits and leaked stack traces

**Vulnerability:** The CLI did not place bounds on properties like `--size` or `--food`, which permitted the application to allocate extremely large grids when requested, exposing it to memory exhaustion Denial of Service (DoS) attacks. Furthermore, unhandled exceptions were leaking full stack traces to the output, thereby exposing internal application architecture.
**Learning:** `argparse` types can be mapped to customized validator functions to check limits rather than just parsing raw primitive types. Missing boundary constraints on arguments that trigger memory allocation lead directly to a vulnerability.
**Prevention:** Bound variables that determine the size of allocated structures to safe upper limits using argument parsing. Wrap entry points with generic exception handlers to prevent raw exception leakage to users.
