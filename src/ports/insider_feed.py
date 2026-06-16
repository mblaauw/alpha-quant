from abc import ABC, abstractmethod

from domain.models import InsiderCluster, InsiderTransaction


class InsiderFeed(ABC):
    @abstractmethod
    def cluster_transactions(self, symbol: str) -> list[InsiderTransaction]: ...

    @abstractmethod
    def recent_clusters(self, symbol: str) -> list[InsiderCluster]: ...
