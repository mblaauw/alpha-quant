"""Domain-specific exception types."""


class AlphaQuantError(Exception): ...


class DataNormalizationError(AlphaQuantError):
    def __init__(self, message: str, *, source: str = "", raw: str = "") -> None:
        self.source = source
        self.raw = raw
        super().__init__(message)
