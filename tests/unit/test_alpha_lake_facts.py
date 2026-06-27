from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alpha_quant.adapters._parse import (
    parse_facts_bundle,
    parse_readout_item,
    parse_symbol_mutation_result,
    parse_symbol_registry_item,
)
from alpha_quant.adapters.fake.alpha_lake_http_fixture import (
    AlphaLakeHttpFixtureClient,
)
from alpha_quant.contracts.alpha_lake import (
    FactsBundle,
    FactsBundleMetadata,
    FactsBundleSections,
    ReadoutDefinition,
    ReadoutItem,
    ReadoutObservation,
    SymbolMutationResult,
    SymbolRegistryItem,
)


class TestFactsBundleContracts:
    def test_readout_definition_defaults(self) -> None:
        d = ReadoutDefinition(readout_id="rsi_14", label="RSI (14)", category="momentum")
        assert d.readout_id == "rsi_14"
        assert d.unit == ""

    def test_readout_observation_defaults(self) -> None:
        o = ReadoutObservation(effective_date="2026-06-26")
        assert o.value is None
        assert o.normalized is None

    def test_readout_item(self) -> None:
        item = ReadoutItem(
            definition=ReadoutDefinition(
                readout_id="rsi_14", label="RSI (14)", category="momentum"
            ),
            observations=[
                ReadoutObservation(effective_date="2026-06-26", value=65.2, normalized=0.65)
            ],
        )
        assert item.definition.readout_id == "rsi_14"
        assert len(item.observations) == 1
        assert item.observations[0].value == 65.2

    def test_facts_bundle_metadata_defaults(self) -> None:
        as_of = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
        m = FactsBundleMetadata(symbol="AAPL", as_of=as_of)
        assert m.snapshot_id is None
        assert m.categories == []

    def test_facts_bundle_sections_defaults(self) -> None:
        s = FactsBundleSections()
        assert s.readouts == []
        assert s.fundamentals == []

    def test_facts_bundle(self) -> None:
        as_of = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
        bundle = FactsBundle(
            metadata=FactsBundleMetadata(symbol="AAPL", as_of=as_of),
            sections=FactsBundleSections(
                readouts=[
                    ReadoutItem(
                        definition=ReadoutDefinition(
                            readout_id="rsi_14", label="RSI (14)", category="momentum"
                        ),
                        observations=[ReadoutObservation(effective_date="2026-06-26", value=65.2)],
                    )
                ]
            ),
        )
        assert bundle.metadata.symbol == "AAPL"
        assert len(bundle.sections.readouts) == 1

    def test_symbol_registry_item(self) -> None:
        item = SymbolRegistryItem(symbol="AAPL", added_at="2026-06-01", active=True)
        assert item.symbol == "AAPL"

    def test_symbol_mutation_result(self) -> None:
        r = SymbolMutationResult(symbol="AAPL", status="added")
        assert r.status == "added"


class TestFactsBundleParsing:
    def test_parse_facts_bundle(self) -> None:
        raw = {
            "symbol": "AAPL",
            "as_of": "2026-06-27T12:00:00Z",
            "snapshot_id": "snap_123",
            "categories": ["momentum", "fundamental"],
            "readouts": [
                {
                    "definition": {
                        "readout_id": "rsi_14",
                        "label": "RSI (14)",
                        "category": "momentum",
                        "unit": "",
                    },
                    "observations": [
                        {
                            "effective_date": "2026-06-26",
                            "value": 65.2,
                            "normalized": 0.65,
                        }
                    ],
                }
            ],
            "fundamentals": [],
            "insider_transactions": [],
            "earnings_events": [],
            "attention_mentions": [],
        }
        bundle = parse_facts_bundle(raw)
        assert bundle.metadata.symbol == "AAPL"
        assert bundle.metadata.snapshot_id == "snap_123"
        assert len(bundle.sections.readouts) == 1
        assert bundle.sections.readouts[0].definition.readout_id == "rsi_14"
        assert bundle.sections.readouts[0].observations[0].value == 65.2

    def test_parse_facts_bundle_empty(self) -> None:
        raw = {
            "symbol": "AAPL",
            "as_of": "2026-06-27T12:00:00Z",
        }
        bundle = parse_facts_bundle(raw)
        assert bundle.metadata.symbol == "AAPL"
        assert bundle.sections.readouts == []

    def test_parse_symbol_registry_item(self) -> None:
        raw = {"symbol": "AAPL", "added_at": "2026-06-01", "active": True}
        item = parse_symbol_registry_item(raw)
        assert item.symbol == "AAPL"
        assert item.active is True

    def test_parse_symbol_mutation_result(self) -> None:
        raw = {"symbol": "AAPL", "status": "added"}
        r = parse_symbol_mutation_result(raw)
        assert r.symbol == "AAPL"
        assert r.status == "added"

    def test_parse_empty_readout(self) -> None:
        raw = {"definition": {"readout_id": "test", "label": "Test", "category": "x"}}
        item = parse_readout_item(raw)
        assert item.definition.readout_id == "test"
        assert item.observations == []

    def test_parse_multiple_observations(self) -> None:
        raw = {
            "definition": {
                "readout_id": "sma_50",
                "label": "SMA (50)",
                "category": "trend",
            },
            "observations": [
                {"effective_date": "2026-06-25", "value": 150.0},
                {"effective_date": "2026-06-26", "value": 151.5},
            ],
        }
        item = parse_readout_item(raw)
        assert len(item.observations) == 2
        assert item.observations[-1].value == 151.5


class TestFixtureAdapter:
    def test_facts_bundle_empty_fallback(self) -> None:
        client = AlphaLakeHttpFixtureClient(Path("/tmp/nonexistent"))
        as_of = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
        bundle = client.read_facts_bundle("AAPL", as_of)
        assert bundle.metadata.symbol == "AAPL"
        assert bundle.metadata.as_of == as_of

    def test_list_symbols_empty(self) -> None:
        client = AlphaLakeHttpFixtureClient(Path("/tmp/nonexistent"))
        symbols = client.list_symbols()
        assert symbols == []

    def test_add_symbol(self) -> None:
        client = AlphaLakeHttpFixtureClient(Path("/tmp/nonexistent"))
        r = client.add_symbol("AAPL")
        assert r.symbol == "AAPL"
        assert r.status == "added"

    def test_remove_symbol(self) -> None:
        client = AlphaLakeHttpFixtureClient(Path("/tmp/nonexistent"))
        r = client.remove_symbol("AAPL")
        assert r.symbol == "AAPL"
        assert r.status == "removed"
