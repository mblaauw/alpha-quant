from __future__ import annotations

import hashlib
import json

from alpha_quant.contracts.operational import ArtifactReference, ImmutableArtifact


class S3ArtifactStore:
    def __init__(self, bucket: str, *, endpoint_url: str | None = None) -> None:
        import boto3

        self.bucket = bucket
        kwargs = {}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self.client = boto3.client("s3", **kwargs)

    def put_json(self, artifact: ImmutableArtifact) -> ArtifactReference:
        body_bytes = artifact.body.encode("utf-8")
        checksum = artifact.checksum_sha256 or hashlib.sha256(body_bytes).hexdigest()

        self.client.put_object(
            Bucket=self.bucket,
            Key=artifact.key,
            Body=body_bytes,
            ContentType=artifact.content_type,
            Metadata={"sha256": checksum},
        )
        resp = self.client.head_object(Bucket=self.bucket, Key=artifact.key)
        return ArtifactReference(
            key=artifact.key,
            bucket=self.bucket,
            checksum_sha256=checksum,
            size_bytes=resp.get("ContentLength", len(body_bytes)),
        )

    def get_json(self, reference: ArtifactReference) -> dict[str, object]:
        resp = self.client.get_object(Bucket=reference.bucket, Key=reference.key)
        body = resp["Body"].read().decode("utf-8")
        return dict(json.loads(body))

    def verify(self, reference: ArtifactReference) -> bool:
        try:
            resp = self.client.head_object(Bucket=reference.bucket, Key=reference.key)
            meta_checksum = resp.get("Metadata", {}).get("sha256")
            if meta_checksum and reference.checksum_sha256:
                return meta_checksum == reference.checksum_sha256
            return True
        except Exception:
            return False
