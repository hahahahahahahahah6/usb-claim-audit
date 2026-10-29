"""Command line interface."""
import argparse
import json
import sys
from . import __version__
from .audit import audit


def main():
    parser = argparse.ArgumentParser(description="Audit documented wired device claims against Python source.")
    parser.add_argument("root")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--ignore", action="append", default=[])
    parser.add_argument("--fail-on", choices=("HIGH", "MEDIUM"), default="HIGH")
    parser.add_argument("--version", action="version", version=__version__)
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return 1 if exc.code == 2 else exc.code
    try:
        result = audit(args.root, args.ignore, args.fail_on)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result))
    else:
        print(result["verdict"])
        for finding in result["findings"]:
            print("{severity} {rule}: {message}".format(**finding))
        if args.verbose:
            print("Scanned {} files".format(result["scanned"]))
    return 2 if result["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
