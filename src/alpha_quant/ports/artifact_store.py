from __future__ import annotations

from typing import Protocol

from alpha_quant.contracts.operational import ArtifactReference, ImmutableArtifact


class ArtifactStorePort(Protocol):
    def put_json(self, artifact: ImmutableArtifact) -> ArtifactReference: ...
    def get_json(self, reference: ArtifactReference) -> dict[str, object]: ...
    def verify(self, reference: ArtifactReference) -> bool: ...
