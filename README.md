# Module Mirrorer

Mirrors configured repositories to the [dune-mirrors](https://github.com/dune-mirrors) org.

<!-- last-updated:start -->
Mirrors last updated at: 2026-09-26 03:11:16 UTC
<!-- last-updated:end -->


## Configuration

The repositories to be mirrored are defined in `repos.json`. This file contains a JSON object mapping repository names to their GitLab URLs. To add or remove repositories from the mirroring process, simply edit this file and push your changes to trigger an update.

Example format:
```json
{
    "repository-name": "https://gitlab.dune-project.org/path/to/repository.git"
}
```

### Per-repository options

A repository that needs more than a URL may instead map to an object with a
required `url` plus optional settings:

```json
{
    "repository-name": {
        "url": "https://gitlab.dune-project.org/path/to/repository.git",
        "strip_blobs_bigger_than": "100M"
    }
}
```

| Option | Meaning |
|--------|---------|
| `strip_blobs_bigger_than` | Rewrite history with `git-filter-repo` before pushing, removing every blob larger than this (a number with an optional `K`/`M`/`G` suffix). |

**`strip_blobs_bigger_than` rewrites history, so use it only where a mirror is
otherwise impossible.** GitHub refuses any pushed blob over 100 MB (`GH001`)
and declines the *entire* push when it finds one, so a single oversized blob
anywhere in a repository's history freezes that whole mirror — every branch and
tag, not just the ones carrying the blob.

`dune-alugrid` is the one repository in this configuration that hits this. It
carries two benchmark outputs (`results/mb_kway_314/mb.2048.out`, 506 MB, and
`mb.4096.out`, 435 MB) that were committed in February 2014 and deleted again a
fortnight later. They are absent from every current tree but sit in the
ancestry of **82 of its 83** branches and tags, so no choice of refs avoids
them. This is why `dune-mirrors/dune-alugrid` sat frozen at `releases/2.6` with
no tags for years: it was seeded before those commits, and every refresh since
would have been rejected.

Consequences to be aware of before adding this to another repository:

- **The mirror's commit hashes diverge from upstream.** Everything from the
  first affected commit onward is rewritten. Anything pinning a mirror commit
  must pin the *rewritten* hash. (File contents are untouched: the rewritten
  `releases/2.10` tip has the identical tree to its upstream counterpart.)
- **The rewrite must stay reproducible**, or every refresh would produce new
  hashes and break downstream pins. The `git-filter-repo` version is therefore
  pinned in the workflow; bumping it means re-verifying that the hashes are
  unchanged, and treating any change as a breaking one for downstream pins.
- **The first push after enabling this is effectively a force-push**, since it
  replaces whatever the mirror held before.

## Workflow Description

The mirroring process is implemented as a GitHub Actions workflow defined in `.github/workflows/mirrorer.yml`. The workflow operates as follows:

1. **Trigger**: The workflow runs:
   - Automatically every day at midnight (via cron schedule)
   - Manually when triggered via GitHub's workflow_dispatch
   - On push to the repository (e.g., when updating `repos.json`)

2. **Repository Matrix Generation**:
   - The workflow first runs a job that executes `repos_to_matrix.py`
   - This script reads `repos.json` and converts it to a format suitable for GitHub Actions' matrix strategy
   - Each repository is processed with its name, URL, and a keyname (used for SSH key reference)

3. **Mirroring Process**:
   - For each repository in the matrix, a separate job runs in parallel
   - The job mints a short-lived installation token from the **DUNE Mirrorer** GitHub App
     (its private key is stored in the `DUNE_MIRRORER_PRIVATE_KEY` secret), scoped to just the
     target mirror repository
   - It clones the GitLab repository with `--mirror` option to get all branches and tags
   - Sets the push URL to the corresponding repository in the dune-mirrors GitHub organization
   - Removes the GitLab merge-request references (which GitHub rejects on push)
   - Pushes all branches and tags to GitHub with `--mirror` option, authenticating with the App token

### Authentication

Pushes to the `dune-mirrors` org are authenticated with the **DUNE Mirrorer** GitHub App
rather than per-repository SSH deploy keys. The App must be installed on the organization
with **Contents: write** permission and granted access to the mirror repositories. Only its
private key (the `DUNE_MIRRORER_PRIVATE_KEY` Actions secret) needs to be configured.

The `update-readme` job also pushes the "last updated" timestamp back to the protected
`main` branch. `main` requires the `mirror-success` status check, which a fresh `[skip ci]`
commit can never carry on its own SHA, and the App's pull-request bypass does not waive
required status checks. The job therefore publishes the commit on a throwaway branch,
asserts `mirror-success` on that commit via the GitHub Statuses API, then fast-forwards
`main`. For this the App additionally needs **Commit statuses: write** permission and must
be on the branch protection "allow specified actors to bypass required pull requests" list.

## Installation and Dependencies

This project uses `pyproject.toml` for dependency management. The required dependencies are:
- requests: For making HTTP requests to the GitHub API
- python-dotenv: For loading environment variables from .env files

### Installing Dependencies

To install the dependencies, you can use pip:

```bash
# Install the base dependencies
pip install -e .

# For development (includes testing and linting tools)
pip install -e ".[dev]"
```

## Usage

- **Add/Remove Repositories**: Edit `repos.json` and push changes
- **Manual Trigger**: Use the "Run workflow" button in the Actions tab of the GitHub repository
- **Automatic Updates**: The workflow runs daily to ensure mirrors stay up-to-date

### Local Development

To run the scripts locally:

1. Create a `.env` file with your GitHub token:
   ```
   GITHUB_TOKEN=your_github_token
   ```

2. Run the infrastructure setup script (ensures each mirror repo exists in the org;
   authentication for pushes is handled by the DUNE Mirrorer GitHub App):
   ```bash
   python infra_setup.py
   ```

3. Generate the repository matrix:
   ```bash
   python repos_to_matrix.py
   ```
