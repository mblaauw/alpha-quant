# ADR-0058: Removal of CLI run/status/journal/ask/report/halt/backup Commands

## Status

Accepted

## Date

2026-06-30

## Context

Alpha-Quant previously had CLI commands for running the daily pipeline, viewing status, journal, asking LLM questions, generating reports, managing halts, and backing up state. These were replaced by the Desk SPA and command bus.

## Decision

The CLI is limited to infrastructure commands: dashboard, worker, db-*. All operational interactions go through the Desk SPA.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.

