import json
import sys
from pathlib import Path

REPOS_FILE = Path("repos.json")


def fail(message):
    """Print an error to stderr and exit non-zero."""
    print(f"repos_to_matrix: error: {message}", file=sys.stderr)
    sys.exit(1)


def load_repos():
    """Load and validate the repository configuration from repos.json."""
    if not REPOS_FILE.exists():
        fail(f"{REPOS_FILE} not found (run from the repository root)")

    try:
        with REPOS_FILE.open() as f:
            repos = json.load(f)
    except json.JSONDecodeError as exc:
        fail(f"{REPOS_FILE} is not valid JSON: {exc}")

    if not isinstance(repos, dict) or not repos:
        fail(f"{REPOS_FILE} must be a non-empty JSON object mapping name -> URL")

    for name, url in repos.items():
        if not isinstance(url, str) or not url.strip():
            fail(f"repository '{name}' has an empty or non-string URL")
        if not url.startswith(("http://", "https://", "git@")):
            fail(f"repository '{name}' has a URL that does not look like a git remote: {url!r}")

    return repos


def build_matrix(repos):
    """Build the GitHub Actions matrix include list from the repo config."""
    return {"include": [{"module_name": repo, "url": url} for repo, url in repos.items()]}


def main():
    repos = load_repos()
    matrix = build_matrix(repos)

    # stdout is captured into GITHUB_OUTPUT by the workflow, so it must contain
    # ONLY the matrix JSON. All diagnostics go to stderr.
    names = ", ".join(repos)
    print(f"repos_to_matrix: built matrix for {len(repos)} repos: {names}", file=sys.stderr)

    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
