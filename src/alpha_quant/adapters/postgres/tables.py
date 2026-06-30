from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry

from alpha_quant.contracts.operational import (
    FillQuality,
    HaltReason,
    OrderSide,
    OrderStatus,
    RunKind,
    RunStatus,
)


class Base(DeclarativeBase):
    registry = registry(
        type_annotation_map={
            Decimal: Numeric(28, 10),
            UUID: String(36),
        }
    )


def str_10():
    return mapped_column(String(10), nullable=False)


def str_20():
    return mapped_column(String(20), nullable=False)


def str_24():
    return mapped_column(String(24), nullable=False)


def str_36():
    return mapped_column(String(36), nullable=False)


def str_255():
    return mapped_column(String(255), nullable=False)


def str_64():
    return mapped_column(String(64), nullable=False)


def text_field():
    return mapped_column(Text, nullable=False)


def dec_field():
    return mapped_column(Numeric(28, 10), nullable=False)


def int_field():
    return mapped_column(Integer, nullable=False)


def bool_field():
    return mapped_column(Boolean, nullable=False, default=False)


def dt_field():
    return mapped_column(DateTime(timezone=True), nullable=False)


def dt_opt():
    return mapped_column(DateTime(timezone=True), nullable=True)


def date_field():
    return mapped_column(Date, nullable=False)


def date_opt():
    return mapped_column(Date, nullable=True)


def enum_field(e: type[PyEnum]):
    return mapped_column(SAEnum(e, create_constraint=False), nullable=False)


def enum_opt(e: type[PyEnum]):
    return mapped_column(SAEnum(e, create_constraint=False), nullable=True)


def pk_uuid():
    return mapped_column(String(36), primary_key=True)


def fk(ref: str):
    return mapped_column(String(36), ForeignKey(ref), nullable=False)


def fk_opt(ref: str):
    return mapped_column(String(36), ForeignKey(ref), nullable=True)


class Strategy(Base):
    __tablename__ = "strategy"
    __table_args__ = {"schema": "core"}

    strategy_id: Mapped[str] = pk_uuid()
    name: Mapped[str] = str_255()
    created_at: Mapped[datetime] = dt_field()


class StrategyVersion(Base):
    __tablename__ = "strategy_version"
    __table_args__ = {"schema": "core"}

    strategy_version_id: Mapped[str] = pk_uuid()
    strategy_id: Mapped[str] = fk("core.strategy.strategy_id")
    version_label: Mapped[str] = str_64()
    config_json: Mapped[str] = text_field()
    config_hash: Mapped[str] = str_64()
    created_at: Mapped[datetime] = dt_field()


class PortfolioBook(Base):
    __tablename__ = "portfolio_book"
    __table_args__ = {"schema": "core"}

    book_id: Mapped[str] = pk_uuid()
    name: Mapped[str] = str_64()
    kind: Mapped[str] = str_64()
    created_at: Mapped[datetime] = dt_field()


class SecurityReference(Base):
    __tablename__ = "security_reference"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_security_reference_symbol"),
        CheckConstraint("symbol != ''", name="ck_security_symbol_not_empty"),
        {"schema": "core"},
    )

    security_id: Mapped[str] = pk_uuid()
    symbol: Mapped[str] = str_36()
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ExecutionProfile(Base):
    __tablename__ = "execution_profile"
    __table_args__ = {"schema": "core"}

    profile_id: Mapped[str] = pk_uuid()
    name: Mapped[str] = str_64()
    slippage_bps: Mapped[int] = int_field()
    spread_model: Mapped[str] = str_64()


class DecisionRun(Base):
    __tablename__ = "decision_run"
    __table_args__ = {"schema": "run"}

    decision_run_id: Mapped[str] = pk_uuid()
    run_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    run_kind: Mapped[RunKind] = enum_field(RunKind)
    status: Mapped[RunStatus] = enum_field(RunStatus)
    strategy_version_id: Mapped[str] = fk("core.strategy_version.strategy_version_id")
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    decision_as_of: Mapped[datetime] = dt_field()
    execution_as_of: Mapped[datetime | None] = dt_opt()
    resolved_snapshot_id: Mapped[str] = str_64()
    alpha_lake_api_version: Mapped[str] = str_64()
    alpha_lake_contract_version: Mapped[str] = str_64()
    config_hash: Mapped[str] = str_64()
    request_hash: Mapped[str] = str_64()
    response_hash: Mapped[str] = str_64()
    started_at: Mapped[datetime] = dt_field()
    completed_at: Mapped[datetime | None] = dt_opt()
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlphaLakeManifest(Base):
    __tablename__ = "alpha_lake_manifest"
    __table_args__ = {"schema": "run"}

    manifest_id: Mapped[str] = pk_uuid()
    decision_run_id: Mapped[str] = fk("run.decision_run.decision_run_id")
    request_body: Mapped[str] = text_field()
    response_body: Mapped[str] = text_field()
    snapshot_id: Mapped[str] = str_64()
    contract_version: Mapped[str] = str_64()
    api_version: Mapped[str] = str_64()
    request_hash: Mapped[str] = str_64()
    response_hash: Mapped[str] = str_64()
    created_at: Mapped[datetime] = dt_field()


class CandidateEvaluation(Base):
    __tablename__ = "candidate_evaluation"
    __table_args__ = (
        CheckConstraint("composite_score >= 0", name="ck_candidate_composite_nonneg"),
        Index("ix_candidate_evaluation_decision_run_id", "decision_run_id"),
        Index("ix_candidate_security_id", "security_id"),
        {"schema": "run"},
    )

    candidate_id: Mapped[str] = pk_uuid()
    decision_run_id: Mapped[str] = fk("run.decision_run.decision_run_id")
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    security_id: Mapped[str] = fk("core.security_reference.security_id")
    symbol: Mapped[str] = str_36()
    composite_score: Mapped[Decimal] = dec_field()
    regime: Mapped[str] = str_64()
    blocked: Mapped[bool] = bool_field()
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate_results: Mapped[str] = text_field()


class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluation"
    __table_args__ = (
        Index("ix_policy_evaluation_candidate_id", "candidate_id"),
        {"schema": "run"},
    )

    evaluation_id: Mapped[str] = pk_uuid()
    candidate_id: Mapped[str] = fk("run.candidate_evaluation.candidate_id")
    policy_name: Mapped[str] = str_64()
    policy_version: Mapped[str] = str_64()
    score: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str] = text_field()


class PaperOrder(Base):
    __tablename__ = "paper_order"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_paper_order_quantity_positive"),
        Index("ix_paper_order_decision_run_id", "decision_run_id"),
        Index("ix_paper_order_book_id", "portfolio_book_id"),
        {"schema": "trade"},
    )

    order_id: Mapped[str] = pk_uuid()
    decision_run_id: Mapped[str | None] = fk_opt("run.decision_run.decision_run_id")
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    security_id: Mapped[str] = fk("core.security_reference.security_id")
    symbol: Mapped[str] = str_36()
    side: Mapped[OrderSide] = enum_field(OrderSide)
    quantity: Mapped[Decimal] = dec_field()
    status: Mapped[OrderStatus] = enum_field(OrderStatus)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    submitted_at: Mapped[datetime | None] = dt_opt()
    filled_quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)


class PaperFill(Base):
    __tablename__ = "paper_fill"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_paper_fill_quantity_positive"),
        CheckConstraint("price > 0", name="ck_paper_fill_price_positive"),
        Index("ix_paper_fill_security_id", "security_id"),
        Index("ix_paper_fill_order_id", "order_id"),
        {"schema": "trade"},
    )

    fill_id: Mapped[str] = pk_uuid()
    order_id: Mapped[str] = fk("trade.paper_order.order_id")
    security_id: Mapped[str] = fk("core.security_reference.security_id")
    symbol: Mapped[str] = str_36()
    side: Mapped[OrderSide] = enum_field(OrderSide)
    quantity: Mapped[Decimal] = dec_field()
    price: Mapped[Decimal] = dec_field()
    fill_key: Mapped[str] = mapped_column(String(255), nullable=False)
    quality: Mapped[FillQuality] = enum_field(FillQuality)
    fee: Mapped[Decimal] = dec_field()
    booked_at: Mapped[datetime | None] = dt_opt()


class CashLedgerEntry(Base):
    __tablename__ = "cash_ledger_entry"
    __table_args__ = (
        CheckConstraint("amount != 0", name="ck_cash_ledger_amount_nonzero"),
        Index("ix_cash_ledger_fill_id", "fill_id"),
        Index("ix_cash_ledger_book_id", "portfolio_book_id"),
        {"schema": "trade"},
    )

    entry_id: Mapped[str] = pk_uuid()
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    fill_id: Mapped[str | None] = fk_opt("trade.paper_fill.fill_id")
    amount: Mapped[Decimal] = dec_field()
    currency: Mapped[str] = str_36()
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    booked_at: Mapped[datetime | None] = dt_opt()


class CorporateActionBooking(Base):
    __tablename__ = "corporate_action_booking"
    __table_args__ = {"schema": "trade"}

    booking_id: Mapped[str] = pk_uuid()
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    security_id: Mapped[str] = fk("core.security_reference.security_id")
    action_type: Mapped[str] = str_64()
    effective_date: Mapped[datetime] = date_field()
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)


class PortfolioMark(Base):
    __tablename__ = "portfolio_mark"
    __table_args__ = (
        UniqueConstraint("portfolio_book_id", "effective_date", name="uq_portfolio_mark_book_date"),
        {"schema": "trade"},
    )

    mark_id: Mapped[str] = pk_uuid()
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    effective_date: Mapped[datetime] = date_field()
    cash: Mapped[Decimal] = dec_field()
    equity: Mapped[Decimal] = dec_field()
    gross_exposure: Mapped[Decimal] = dec_field()
    regime: Mapped[str] = str_64()
    mark_as_of: Mapped[datetime] = dt_field()


class PositionCurrent(Base):
    __tablename__ = "position_current"
    __table_args__ = (
        CheckConstraint("NOT (quantity = 0 AND avg_cost != 0)", name="ck_position_stale_check"),
        Index("ix_position_current_book_id", "book_id"),
        {"schema": "projection"},
    )

    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.portfolio_book.book_id"), primary_key=True
    )
    security_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.security_reference.security_id"), primary_key=True
    )
    symbol: Mapped[str] = str_36()
    quantity: Mapped[Decimal] = dec_field()
    avg_cost: Mapped[Decimal] = dec_field()
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    unrealized_pl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)


class PortfolioCurrent(Base):
    __tablename__ = "portfolio_current"
    __table_args__ = {"schema": "projection"}

    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.portfolio_book.book_id"), primary_key=True
    )
    cash: Mapped[Decimal] = dec_field()
    equity: Mapped[Decimal] = dec_field()
    gross_exposure: Mapped[Decimal] = dec_field()
    regime: Mapped[str] = str_64()
    updated_at: Mapped[datetime] = dt_field()


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_decision_run_id", "decision_run_id"),
        {"schema": "audit"},
    )

    event_id: Mapped[str] = pk_uuid()
    decision_run_id: Mapped[str] = fk_opt("run.decision_run.decision_run_id")
    event_type: Mapped[str] = str_64()
    payload_json: Mapped[str] = text_field()
    created_at: Mapped[datetime] = dt_field()


class RiskEvent(Base):
    __tablename__ = "risk_event"
    __table_args__ = {"schema": "audit"}

    risk_event_id: Mapped[str] = pk_uuid()
    decision_run_id: Mapped[str] = fk("run.decision_run.decision_run_id")
    event_type: Mapped[str] = str_64()
    severity: Mapped[str] = str_36()
    details_json: Mapped[str] = text_field()
    created_at: Mapped[datetime] = dt_field()


class HaltTransition(Base):
    __tablename__ = "halt_transition"
    __table_args__ = {"schema": "audit"}

    halt_id: Mapped[str] = pk_uuid()
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    reason: Mapped[HaltReason] = enum_field(HaltReason)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    halted_at: Mapped[datetime] = dt_field()
    resumed_at: Mapped[datetime | None] = dt_opt()


class CurrentHalt(Base):
    __tablename__ = "current_halt"
    __table_args__ = {"schema": "ops"}

    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.portfolio_book.book_id"), primary_key=True
    )
    halted: Mapped[bool] = bool_field()
    reason: Mapped[HaltReason | None] = enum_opt(HaltReason)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    halted_at: Mapped[datetime | None] = dt_opt()


class Command(Base):
    __tablename__ = "command"
    __table_args__ = (
        UniqueConstraint("actor_id", "type", "idempotency_key", name="uq_command_idempotency"),
        Index("ix_command_status", "status"),
        {"schema": "ops"},
    )

    command_id: Mapped[str] = pk_uuid()
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = str_64()
    actor_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    book_id: Mapped[str | None] = fk_opt("core.portfolio_book.book_id")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str] = text_field()
    result_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = dt_field()
    started_at: Mapped[datetime | None] = dt_opt()
    finished_at: Mapped[datetime | None] = dt_opt()


class RunLockAudit(Base):
    __tablename__ = "run_lock_audit"
    __table_args__ = {"schema": "ops"}

    lock_id: Mapped[str] = pk_uuid()
    run_key: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = str_36()
    created_at: Mapped[datetime] = dt_field()


class AppConfig(Base):
    __tablename__ = "app_config"
    __table_args__ = {"schema": "ops"}

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = dt_field()


class RiskMethod(Base):
    __tablename__ = "risk_method"
    __table_args__ = (
        CheckConstraint("is_active IS NOT NULL", name="ck_risk_method_active_not_null"),
        {"schema": "core"},
    )

    risk_method_id: Mapped[str] = pk_uuid()
    name: Mapped[str] = str_64()
    description: Mapped[str] = mapped_column(Text, nullable=False)
    method_type: Mapped[str] = str_36()
    default_params_json: Mapped[str] = text_field()
    is_active: Mapped[bool] = bool_field()


class ScorecardOrm(Base):
    __tablename__ = "scorecard"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_scorecard_confidence_range"
        ),
        CheckConstraint("total_score >= 0", name="ck_scorecard_total_score_nonneg"),
        Index("ix_scorecard_decision_run_id", "decision_run_id"),
        Index("ix_scorecard_security_id", "security_id"),
        {"schema": "run"},
    )

    scorecard_id: Mapped[str] = pk_uuid()
    decision_run_id: Mapped[str] = fk("run.decision_run.decision_run_id")
    portfolio_book_id: Mapped[str] = fk("core.portfolio_book.book_id")
    symbol: Mapped[str] = str_36()
    security_id: Mapped[str] = fk("core.security_reference.security_id")
    as_of: Mapped[datetime] = dt_field()
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    facts_hash: Mapped[str] = str_64()
    config_hash: Mapped[str] = str_64()
    strategy_version: Mapped[str] = str_64()
    recommendation: Mapped[str] = str_24()
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    data_quality: Mapped[str] = str_10()
    created_at: Mapped[datetime] = dt_field()


class ScorecardComponentOrm(Base):
    __tablename__ = "scorecard_component"
    __table_args__ = (
        CheckConstraint("score >= 0", name="ck_component_score_nonneg"),
        CheckConstraint("weight > 0", name="ck_component_weight_positive"),
        Index("ix_scorecard_component_scorecard_id", "scorecard_id"),
        {"schema": "run"},
    )

    component_id: Mapped[str] = pk_uuid()
    scorecard_id: Mapped[str] = fk("run.scorecard.scorecard_id")
    name: Mapped[str] = str_64()
    category: Mapped[str] = str_64()
    score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    state: Mapped[str] = str_10()
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    passed: Mapped[bool] = bool_field()
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str] = text_field()


class AdviceArtifactOrm(Base):
    __tablename__ = "advice_artifact"
    __table_args__ = (
        Index("ix_advice_artifact_scorecard_id", "scorecard_id"),
        {"schema": "run"},
    )

    advice_id: Mapped[str] = pk_uuid()
    scorecard_id: Mapped[str] = fk("run.scorecard.scorecard_id")
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recommendation: Mapped[str] = str_24()
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_json: Mapped[str] = text_field()
    risks_json: Mapped[str] = text_field()
    confidence_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    what_changed_json: Mapped[str] = text_field()
    override_guidance_json: Mapped[str] = text_field()
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="scorecard_overall"
    )
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    interpretation: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    key_evidence_json: Mapped[str] = text_field()
    key_caveats_json: Mapped[str] = text_field()
    data_quality_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_context: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    educational_context: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    what_could_change_json: Mapped[str] = text_field()
    deterministic_differs: Mapped[bool] = bool_field()
    created_at: Mapped[datetime] = dt_field()


class OperatorOverrideOrm(Base):
    __tablename__ = "operator_override"
    __table_args__ = {"schema": "audit"}

    override_id: Mapped[str] = pk_uuid()
    scorecard_id: Mapped[str] = fk("run.scorecard.scorecard_id")
    command_id: Mapped[str] = fk("ops.command.command_id")
    actor_id: Mapped[str] = str_64()
    original_recommendation: Mapped[str] = str_24()
    original_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    override_action: Mapped[str] = str_10()
    modified_recommendation: Mapped[str | None] = str_24()
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = dt_field()


class PositionRiskCurrent(Base):
    __tablename__ = "position_risk_current"
    __table_args__ = (
        Index("ix_position_risk_current_book_id", "book_id"),
        {"schema": "projection"},
    )

    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.portfolio_book.book_id"), primary_key=True
    )
    security_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.security_reference.security_id"), primary_key=True
    )
    risk_method_id: Mapped[str | None] = fk_opt("core.risk_method.risk_method_id")
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    trail_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    trail_activation_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    time_stop_date: Mapped[datetime | None] = date_opt()
    auto_trail_enabled: Mapped[bool] = bool_field()
    last_adjusted_at: Mapped[datetime | None] = dt_opt()
    last_adjustment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class RiskPolicyVersion(Base):
    __tablename__ = "risk_policy_version"
    __table_args__ = {"schema": "core"}

    version_label: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_json: Mapped[str] = text_field()
    config_hash: Mapped[str] = str_64()
    created_at: Mapped[datetime] = dt_field()
    last_adjustment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BookRiskProfile(Base):
    __tablename__ = "book_risk_profile"
    __table_args__ = {"schema": "core"}

    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.portfolio_book.book_id"), primary_key=True
    )
    risk_method_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("core.risk_method.risk_method_id"), nullable=False
    )
    params_json: Mapped[str] = text_field()
    updated_at: Mapped[datetime] = dt_field()
