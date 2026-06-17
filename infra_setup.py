#!/usr/bin/env python3
"""One-off infrastructure setup for the GitHub mirrors.

Authentication for pushing to the mirrors is handled at run time by the
"DUNE Mirrorer" GitHub App (see .github/workflows/mirrorer.yml), so this script
only has to make sure each configured mirror repository exists in the
dune-mirrors organization. The GitHub App itself must be installed on the
organization with "Contents: write" permission and granted access to these
repositories.
"""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# HTTP status codes
HTTP_OK = 200
HTTP_CREATED = 201

# Load environment variables from .env file
load_dotenv()

# Get GitHub token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in .env file")

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"
GITHUB_ORG = "dune-mirrors"

# Headers for GitHub API requests
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def load_repos():
    """Load repository configuration from repos.json"""
    with Path("repos.json").open() as f:
        return json.load(f)


def create_repo_if_not_exists(repo_name):
    """Create a repository in the dune-mirrors organization if it doesn't exist.

    Returns True if a new repository was created, False if it already existed.
    """
    print(f"Checking if repository {repo_name} exists in {GITHUB_ORG} organization...")

    # Check if repository exists
    response = requests.get(f"{GITHUB_API_URL}/repos/{GITHUB_ORG}/{repo_name}", headers=headers)

    if response.status_code == HTTP_OK:
        print(f"Repository {repo_name} already exists.")
        return False

    print(f"Creating repository {repo_name} in {GITHUB_ORG} organization...")

    # Create repository
    response = requests.post(
        f"{GITHUB_API_URL}/orgs/{GITHUB_ORG}/repos",
        headers=headers,
        json={
            "name": repo_name,
            "description": f"Mirror of {repo_name}",
            "private": False,
            "has_issues": False,
            "has_projects": False,
            "has_wiki": False,
        },
    )

    if response.status_code != HTTP_CREATED:
        raise Exception(f"Failed to create repository (HTTP {response.status_code}): {response.text}")

    print(f"Repository {repo_name} created successfully.")
    return True


def main():
    """Main function"""
    print("Starting infrastructure setup...")

    # Load repository configuration
    repos = load_repos()
    total = len(repos)
    created = 0
    existing = 0

    for index, repo_name in enumerate(repos, start=1):
        print(f"\n[{index}/{total}] Processing repository: {repo_name}")

        # Create repository if it doesn't exist
        if create_repo_if_not_exists(repo_name):
            created += 1
        else:
            existing += 1

    print("\nInfrastructure setup completed successfully.")
    print(f"Summary: {total} repo(s) processed ({created} created, {existing} already existed).")
    print(
        "\nReminder: pushing is handled by the 'DUNE Mirrorer' GitHub App. Ensure the app is "
        "installed on the dune-mirrors org with 'Contents: write' permission and granted access "
        "to the repositories above.",
    )


if __name__ == "__main__":
    main()
