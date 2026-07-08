from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    try:
        from app.ui.dashboard import render_dashboard
    except RuntimeError as exc:
        print(exc)
        return
    render_dashboard()


if __name__ == "__main__":
    main()
