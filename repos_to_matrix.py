import json
import re
import sys
from pathlib import Path

REPOS_FILE = Path("repos.json")

# git-filter-repo's --strip-blobs-bigger-than syntax: a number with an optional
# K/M/G suffix (bare numbers are bytes).
SIZE_RE = re.compile(r"^\d+[KMG]?$")


def fail(message):
    """Print an error to stderr and exit non-zero."""
    print(f"repos_to_matrix: error: {message}", file=sys.stderr)
    sys.exit(1)


def normalize_entry(name, entry):
    """Normalize one repos.json value into a {url, strip_blobs_bigger_than} dict.

    An entry is either a plain URL string, or an object with a required "url"
    plus optional per-repository settings.
    """
    if isinstance(entry, str):
        entry = {"url": entry}

    if not isinstance(entry, dict):
        fail(f"repository '{name}' must map to a URL string or an object, got {type(entry).__name__}")

    unknown = set(entry) - {"url", "strip_blobs_bigger_than"}
    if unknown:
        fail(f"repository '{name}' has unknown key(s): {', '.join(sorted(unknown))}")

    url = entry.get("url")
    if not isinstance(url, str) or not url.strip():
        fail(f"repository '{name}' has an empty or non-string URL")
    if not url.startswith(("http://", "https://", "git@")):
        fail(f"repository '{name}' has a URL that does not look like a git remote: {url!r}")

    strip_blobs = entry.get("strip_blobs_bigger_than", "")
    if not isinstance(strip_blobs, str):
        fail(f"repository '{name}' has a non-string strip_blobs_bigger_than: {strip_blobs!r}")
    if strip_blobs and not SIZE_RE.match(strip_blobs):
        fail(
            f"repository '{name}' has an invalid strip_blobs_bigger_than: {strip_blobs!r} "
            "(expected a number with an optional K/M/G suffix, e.g. '100M')",
        )

    return {"url": url, "strip_blobs_bigger_than": strip_blobs}


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

    return {name: normalize_entry(name, entry) for name, entry in repos.items()}


def build_matrix(repos):
    """Build the GitHub Actions matrix include list from the repo config."""
    return {
        "include": [
            {
                "module_name": repo,
                "url": config["url"],
                "strip_blobs_bigger_than": config["strip_blobs_bigger_than"],
            }
            for repo, config in repos.items()
        ],
    }


def main():
    repos = load_repos()
    matrix = build_matrix(repos)

    # stdout is captured into GITHUB_OUTPUT by the workflow, so it must contain
    # ONLY the matrix JSON. All diagnostics go to stderr.
    names = ", ".join(repos)
    print(f"repos_to_matrix: built matrix for {len(repos)} repos: {names}", file=sys.stderr)
    for name, config in repos.items():
        if config["strip_blobs_bigger_than"]:
            print(
                f"repos_to_matrix: {name}: stripping blobs bigger than {config['strip_blobs_bigger_than']}",
                file=sys.stderr,
            )

    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
