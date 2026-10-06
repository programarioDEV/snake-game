## 2026-10-06 - [Missing Input Length Limits]
**Vulnerability:** The application was vulnerable to uncontrolled memory allocation and DoS via unbound grid dimensions in the Grid constructor and CLI parsing.
**Learning:** `argparse` type functions are perfect for boundary checking before the core logic even receives the variables. Defense in Depth dictates adding limits at both `argparse` and the `Grid` model.
**Prevention:** Make sure constructors checking input constraints (like `self.width < 2`) also have reasonable maximum thresholds (like `self.width > 256`), or use limits in `argparse`.
