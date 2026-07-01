# Cron Fallback — Scheduler

If APScheduler is unavailable or unreliable, use the system cron daemon as a fallback.

## crontab entry

```cron
# Alpha-Quant daily pipeline — 17:30 ET (21:30 UTC / 22:30 UTC during EDT)
# Trading days only; cron does not skip weekends/holidays, so the pipeline
# itself checks is_market_day() and exits early on non-trading days.
#
# EDT (Mar–Nov):    UTC-4  →  30 21 * * 1-5
# EST (Nov–Mar):    UTC-5  →  30 22 * * 1-5
#
# Use a single entry that the pipeline validates:

30 21 * * 1-5 cd /path/to/alpha-quant && /path/to/uv run alpha-quant daily-cycle >> logs/cron.out 2>&1
```

## Daylight saving note

- **EDT** (second Sunday Mar → first Sunday Nov): UTC-4 → `30 21 * * 1-5`
- **EST** (first Sunday Nov → second Sunday Mar): UTC-5 → `30 22 * * 1-5`

Change the crontab manually on transition days, or use `@daily` with a TZ-aware check inside the pipeline.

## Idempotency

The pipeline checks the `runs` table for an existing `completed` run on today's date before proceeding. If cron fires twice, the second invocation is a no-op.

## Logging

When running via cron, redirect stdout/stderr to a log file:

```cron
30 21 * * 1-5 cd /path/to/alpha-quant && /path/to/uv run alpha-quant daily-cycle >> logs/cron_pipeline.log 2>&1
```

Maintain the same log retention as the APScheduler setup (30-day rotation via an external `logrotate` config).

## Logrotate config (optional)

```conf
/path/to/alpha-quant/logs/cron_pipeline.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```
