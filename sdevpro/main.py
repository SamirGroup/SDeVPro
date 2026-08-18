"""Entrypoint for the SDeVPro Telegram bot (`sdevpro-bot` console script)."""

from __future__ import annotations

import sys


def cli() -> None:
    from sdevpro.telegram_bot import run

    try:
        run()
    except RuntimeError as exc:
        print(f"[SDeVPro] Ishga tushirib bo'lmadi: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[SDeVPro] To'xtatildi.")  # noqa: T201


if __name__ == "__main__":
    cli()
