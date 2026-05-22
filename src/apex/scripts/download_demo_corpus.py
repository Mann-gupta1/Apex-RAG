"""Download a small public-domain demo corpus into ``data/raw_docs/``.

If the network is unavailable the script writes a small synthetic fallback so
that the rest of the ingestion pipeline always has something to work with.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from apex.logging_config import logger
from apex.settings import get_settings

DEMO_ASSETS = [
    # (relative path under data/raw_docs, url)
    (
        "text/marbury_v_madison.pdf",
        "https://tile.loc.gov/storage-services/service/ll/usrep/usrep005/usrep005137/usrep005137.pdf",
    ),
    (
        "text/brown_v_board.pdf",
        "https://tile.loc.gov/storage-services/service/ll/usrep/usrep347/usrep347483/usrep347483.pdf",
    ),
    (
        "image/supreme_court.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Supreme_Court_Front_Dusk.jpg/1280px-Supreme_Court_Front_Dusk.jpg",
    ),
    (
        "audio/declaration_of_independence_excerpt.mp3",
        "https://ia803005.us.archive.org/30/items/declaration_independence_64kb/declaration_independence_64kb.mp3",
    ),
]

SYNTHETIC_TEXT = """
APEX LEGAL DISCOVERY — INTERNAL MEMO (Synthetic)

In the matter of Acme Corp. v. Beta Industries (Case No. 24-CV-1234), witness
Smith testified during a video deposition recorded on 2024-03-14 that the
contract clause 4.2 was modified verbally on 2023-11-02, two weeks before the
alleged breach. This conflicts with Exhibit 7, a signed amendment dated
2023-12-10. Counsel should cross-reference the audio deposition at timestamp
12:34-14:56 and image Exhibit 3 (the redlined draft).

Recommendation: highlight inconsistency between Smith's testimony and the
documentary evidence in the motion for summary judgment.
""".strip()


def _download(url: str, dst: Path, timeout: float = 30.0) -> bool:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(r.content)
            logger.info("downloaded {} → {}", url, dst.relative_to(get_settings().root_dir))
            return True
    except Exception as exc:
        logger.warning("could not download {}: {}", url, exc)
        return False


def _write_synthetic_fallback(root: Path) -> None:
    target = root / "text" / "apex_legal_memo.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SYNTHETIC_TEXT, encoding="utf-8")
    logger.info("wrote synthetic fallback corpus at {}", target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Apex RAG demo corpus")
    parser.add_argument("--root", default=None, help="Override target root (defaults to data/raw_docs)")
    args = parser.parse_args()

    settings = get_settings()
    root = Path(args.root) if args.root else (settings.root_dir / "data" / "raw_docs")
    root.mkdir(parents=True, exist_ok=True)

    successes = 0
    for rel, url in DEMO_ASSETS:
        dst = root / rel
        if dst.exists() and dst.stat().st_size > 0:
            logger.debug("skip existing {}", dst.name)
            successes += 1
            continue
        if _download(url, dst):
            successes += 1

    if successes == 0:
        logger.warning("no remote assets fetched — writing synthetic fallback")
        _write_synthetic_fallback(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
