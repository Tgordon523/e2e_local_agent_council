"""
Usage:
    python -m council.run "Your idea here"

The idea may also be supplied via the IDEA environment variable (used by the
Docker workflow: `docker-compose run --rm -e IDEA="..." council`).
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # Must run before importing council modules that read os.environ

from council.orchestrator import run_council  # noqa: E402


def main():
    if len(sys.argv) >= 2:
        idea = " ".join(sys.argv[1:])
    elif os.environ.get("IDEA"):
        idea = os.environ["IDEA"]
    else:
        print("Usage: python -m council.run \"<your idea>\"  (or set IDEA env var)")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"IDEA COUNCIL EVALUATION")
    print(f"{'='*60}")
    print(f"Idea: {idea}")
    print(f"{'='*60}\n")

    _run_id, final_verdict = run_council(idea)

    print(f"\n{'='*60}")
    print("FINAL VERDICT")
    print(f"{'='*60}")
    print(final_verdict)


if __name__ == "__main__":
    main()
