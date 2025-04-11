# Module Mirrorer

Mirrors configured repositories to the [dune-mirrors](https://github.com/dune-mirrors) org.

## Configuration

The repositories to be mirrored are defined in `repos.json`. This file contains a JSON object mapping repository names to their GitLab URLs. To add or remove repositories from the mirroring process, simply edit this file and push your changes to trigger an update.

Example format:
```json
{
    "repository-name": "https://gitlab.dune-project.org/path/to/repository.git"
}
```

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
   - The job sets up SSH authentication using repository-specific SSH keys stored as GitHub secrets
   - It clones the GitLab repository with `--mirror` option to get all branches and tags
   - Sets the push URL to the corresponding repository in the dune-mirrors GitHub organization
   - Removes any GitHub-specific pull request references
   - Pushes all branches and tags to GitHub with `--mirror` option

## Installation and Dependencies

This project uses `pyproject.toml` for dependency management. The required dependencies are:
- requests: For making HTTP requests to the GitHub API
- pynacl: For encryption operations
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

2. Run the infrastructure setup script:
   ```bash
   python infra_setup.py
   ```

3. Generate the repository matrix:
   ```bash
   python repos_to_matrix.py
   ```
