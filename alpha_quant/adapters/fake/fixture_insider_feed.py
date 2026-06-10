from alpha_quant.domain.models import InsiderCluster, InsiderTransaction
from alpha_quant.ports.insider_feed import InsiderFeed


class FixtureInsiderFeed(InsiderFeed):
    def __init__(
        self,
        transactions: dict[str, list[InsiderTransaction]] | None = None,
    ) -> None:
        self._transactions: dict[str, list[InsiderTransaction]] = transactions or {}
        self._clusters: dict[str, list[InsiderCluster]] = {}

    def seed_transactions(self, symbol: str, txs: list[InsiderTransaction]) -> None:
        self._transactions[symbol] = txs

    def seed_clusters(self, symbol: str, clusters: list[InsiderCluster]) -> None:
        self._clusters[symbol] = clusters

    async def cluster_transactions(self, symbol: str) -> list[InsiderTransaction]:
        if symbol not in self._transactions:
            msg = f"No fixture insider transactions for symbol: {symbol}"
            raise ValueError(msg)
        return self._transactions[symbol]

    async def recent_clusters(self, symbol: str) -> list[InsiderCluster]:
        return self._clusters.get(symbol, [])
