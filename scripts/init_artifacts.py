"""Idempotent artifact bucket initializer.

Creates the alpha-quant-artifacts bucket if it does not exist.
Safe to run repeatedly — never deletes or overwrites existing data.
"""

from __future__ import annotations

import os

import boto3

BUCKET = "alpha-quant-artifacts"
ENDPOINT = os.environ.get("RUSTFS_ENDPOINT", "http://localhost:9000")
ACCESS_KEY = os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin")
SECRET_KEY = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")


def main() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )
    try:
        client.head_bucket(Bucket=BUCKET)
        print(f"Bucket '{BUCKET}' already exists.")
    except Exception:
        client.create_bucket(Bucket=BUCKET)
        print(f"Created bucket '{BUCKET}'.")


if __name__ == "__main__":
    main()
