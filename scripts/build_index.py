import logging

from parley.rag.ingest import build_index

logging.basicConfig(level=logging.DEBUG)


def main() -> None:
    build_index()


if __name__ == "__main__":
    main()
