import json
import logging
import sys

from parley.agent import ask

logging.basicConfig(level=logging.DEBUG)


def main() -> None:
    question = " ".join(sys.argv[1:]) or "What is the average tip for airport trips?"
    result = ask(question)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
