import logging
from pathlib import Path

import httpx

from parley.config import settings
from parley.rag.documents import TLC_DOC_URLS

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# NYC's server 403s the default urllib User-Agent; send a browser-like one.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; parley-docs-fetch/1.0)"}


def main() -> None:
    directory = Path(settings.docs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    for name, url in TLC_DOC_URLS.items():
        target = directory / name
        if target.exists():
            logger.debug("download_tlc_docs skip existing %s", target)
            continue
        logger.debug("download_tlc_docs fetching %s -> %s", url, target)
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        target.write_bytes(resp.content)
        logger.debug("download_tlc_docs wrote %d bytes -> %s", len(resp.content), target)
    logger.debug("download_tlc_docs complete into %s", directory)


if __name__ == "__main__":
    main()
