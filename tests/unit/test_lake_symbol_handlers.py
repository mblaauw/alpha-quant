from __future__ import annotations

from alpha_quant.application.commands import (
    HANDLERS,
    lake_symbol_add_handler,
    lake_symbol_refresh_handler,
    lake_symbol_remove_handler,
)


class TestLakeSymbolHandlers:
    def test_handlers_registered(self) -> None:
        assert "lake_symbol.add" in HANDLERS
        assert "lake_symbol.remove" in HANDLERS
        assert "lake_symbol.refresh" in HANDLERS

    def test_handler_types(self) -> None:
        assert HANDLERS["lake_symbol.add"] is lake_symbol_add_handler
        assert HANDLERS["lake_symbol.remove"] is lake_symbol_remove_handler
        assert HANDLERS["lake_symbol.refresh"] is lake_symbol_refresh_handler

    def test_add_missing_symbol(self) -> None:
        from uuid import uuid4

        from alpha_quant.contracts.operational import Command, CommandStatus

        cmd = Command(
            command_id=uuid4(),
            type="lake_symbol.add",
            idempotency_key="test",
            status=CommandStatus.REQUESTED,
            actor_id="test",
            actor_display_name="Test",
            payload_json="{}",
            requested_at=None,
        )
        status, result, failure = lake_symbol_add_handler(cmd)
        assert status == CommandStatus.FAILED
        assert failure is not None

    def test_remove_missing_symbol(self) -> None:
        from uuid import uuid4

        from alpha_quant.contracts.operational import Command, CommandStatus

        cmd = Command(
            command_id=uuid4(),
            type="lake_symbol.remove",
            idempotency_key="test",
            status=CommandStatus.REQUESTED,
            actor_id="test",
            actor_display_name="Test",
            payload_json="{}",
            requested_at=None,
        )
        status, result, failure = lake_symbol_remove_handler(cmd)
        assert status == CommandStatus.FAILED

    def test_refresh_missing_symbol(self) -> None:
        from uuid import uuid4

        from alpha_quant.contracts.operational import Command, CommandStatus

        cmd = Command(
            command_id=uuid4(),
            type="lake_symbol.refresh",
            idempotency_key="test",
            status=CommandStatus.REQUESTED,
            actor_id="test",
            actor_display_name="Test",
            payload_json="{}",
            requested_at=None,
        )
        status, result, failure = lake_symbol_refresh_handler(cmd)
        assert status == CommandStatus.FAILED
