#!/usr/bin/env python3
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv
from nacl import public

# HTTP status codes
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
HTTP_UNPROCESSABLE = 422

# Load environment variables from .env file
load_dotenv()

# Get GitHub token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN not found in .env file")

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"
GITHUB_ORG = "dune-mirrors"
CURRENT_REPO = "dune-mirrors/mirrorer"

# Headers for GitHub API requests
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def load_repos():
    """Load repository configuration from repos.json"""
    with Path("repos.json").open() as f:
        return json.load(f)


def generate_ssh_key(repo_name):
    """Generate SSH key pair for a repository"""
    print(f"Generating SSH key for {repo_name}...")

    # Create a temporary directory to store the keys
    with tempfile.TemporaryDirectory() as temp_dir:
        key_file = Path(temp_dir) / "id_rsa"

        # Generate SSH key pair without passphrase
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "rsa",
                "-b",
                "4096",
                "-C",
                f"deploy-key-{repo_name}@dune-mirrors",
                "-f",
                str(key_file),
                "-N",
                "",
            ],
            check=True,
        )

        # Read the private and public keys
        with key_file.open() as f:
            private_key = f.read()

        with Path(f"{key_file}.pub").open() as f:
            public_key = f.read()

        return private_key, public_key


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


def add_deploy_key_to_repo(repo_name, public_key):
    """Add deploy key to a repository (idempotent across re-runs)."""
    print(f"Adding deploy key to {repo_name}...")

    response = requests.post(
        f"{GITHUB_API_URL}/repos/{GITHUB_ORG}/{repo_name}/keys",
        headers=headers,
        json={"title": "Mirror Deploy Key", "key": public_key, "read_only": False},
    )

    if response.status_code == HTTP_CREATED:
        print(f"Deploy key added to {repo_name} successfully.")
        return

    # GitHub returns 422 when the key (or its title) already exists. Treat that as a
    # no-op so re-running setup does not crash on an already-provisioned repo.
    if response.status_code == HTTP_UNPROCESSABLE and "already" in response.text.lower():
        print(f"Deploy key already present on {repo_name}, skipping.")
        return

    raise Exception(f"Failed to add deploy key (HTTP {response.status_code}): {response.text}")


def add_secret_to_mirrorer_repo(secret_name, secret_value):
    """Add a secret to the dune-mirrors/mirrorer repository"""
    print(f"Adding secret {secret_name} to {CURRENT_REPO} repository...")

    # Get the repository's public key for secret encryption
    response = requests.get(
        f"{GITHUB_API_URL}/repos/{CURRENT_REPO}/actions/secrets/public-key",
        headers=headers,
    )

    if response.status_code != HTTP_OK:
        raise Exception(f"Failed to get public key for secrets (HTTP {response.status_code}): {response.text}")

    public_key_data = response.json()
    public_key = public_key_data["key"]
    public_key_id = public_key_data["key_id"]

    # Encrypt the secret value using PyNaCl
    def encrypt(public_key: str, secret_value: str) -> str:
        """Encrypt a string using the provided public key."""
        public_key_bytes = public.PublicKey(base64.b64decode(public_key))
        sealed_box = public.SealedBox(public_key_bytes)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    encrypted_value = encrypt(public_key, secret_value)

    # Send the encrypted secret to GitHub
    response = requests.put(
        f"{GITHUB_API_URL}/repos/{CURRENT_REPO}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": public_key_id},
    )

    if response.status_code not in (HTTP_CREATED, HTTP_NO_CONTENT):
        raise Exception(f"Failed to add secret to repository (HTTP {response.status_code}): {response.text}")

    print(f"Secret {secret_name} added to {CURRENT_REPO} successfully.")


def main():
    """Main function"""
    print("Starting infrastructure setup...")

    # Load repository configuration
    repos = load_repos()
    total = len(repos)
    created = 0
    existing = 0
    secrets_written = 0

    for index, (repo_name, _repo_url) in enumerate(repos.items(), start=1):
        print(f"\n[{index}/{total}] Processing repository: {repo_name}")

        # Generate SSH key pair
        private_key, public_key = generate_ssh_key(repo_name)

        # Create repository if it doesn't exist
        if create_repo_if_not_exists(repo_name):
            created += 1
        else:
            existing += 1

        # Add deploy key to repository
        add_deploy_key_to_repo(repo_name, public_key)

        # Add private key as a secret to the mirrorer repository
        # Replace hyphens with underscores in the repository name for the secret name
        secret_name = f"SSH_KEY_{repo_name.replace('-', '_')}"
        add_secret_to_mirrorer_repo(secret_name, private_key)
        secrets_written += 1

    print("\nInfrastructure setup completed successfully.")
    print(
        f"Summary: {total} repo(s) processed "
        f"({created} created, {existing} already existed), "
        f"{secrets_written} secret(s) written.",
    )


if __name__ == "__main__":
    main()
