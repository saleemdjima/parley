import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from parley.config import settings

logger = logging.getLogger(__name__)

TLC_DOC_URLS = {
    "data_dictionary_trip_records_yellow.pdf": "https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf",
    "trip_record_user_guide.pdf": "https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf",
}


def load_docs(docs_dir: str | None = None) -> list[Document]:
    directory = Path(docs_dir or settings.docs_dir)
    pdfs = sorted(directory.glob("*.pdf"))
    logger.debug("load_docs scanning %s found %d pdfs", directory, len(pdfs))

    if not pdfs:
        raise FileNotFoundError(
            f"No PDFs in {directory}. Run scripts/download_tlc_docs.py first."
        )

    docs: list[Document] = []
    for pdf in pdfs:
        pages = PyPDFLoader(str(pdf)).load()
        logger.debug("load_docs loaded %s pages=%d", pdf.name, len(pages))
        docs.extend(pages)
    return docs
