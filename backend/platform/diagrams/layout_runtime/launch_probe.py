"""Root-installed, opt-in B1 probe; same sandbox, never arbitrary entry points."""

import runpy
import sys

main = runpy.run_path(
    "/opt/stacksense/diagram-artifacts/layout_runtime/launch_elk.py",
    run_name="diagram_launcher",
)["main"]

if __name__ == "__main__":
    try:
        main(proof=True)
    except Exception:
        sys.stderr.write("diagram_proof_unavailable\n")
        raise SystemExit(78) from None
