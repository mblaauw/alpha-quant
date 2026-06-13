# Architecture Documentation

This directory contains the C4 architecture model and views for Alpha-Quant, rendered via LikeC4.

## Contents

| File | Description |
|------|-------------|
| `REFERENCE_ARCHITECTURE.md` | Reference Architecture Document (RAD) — principles, decisions, testing, deployment |
| `model.c4` | LikeC4 DSL — full architecture model (actors, systems, containers, components, deployment, relationships) |
| `views.c4` | LikeC4 DSL — 6 diagram view definitions |
| `views/` | Exported PNG diagrams (see below) |
| `views/index.png` | Auto-generated index of all views |
| `views/systemContext.png` | L1 System Context diagram |
| `views/container.png` | L2 Container diagram |
| `views/dataLayerComponents.png` | L3 Data Layer component diagram |
| `views/decisionEngineComponents.png` | L3 Decision Engine (M1-M8) component diagram |
| `views/fillModelPortfolioComponents.png` | L3 Fill Model & Portfolio component diagram |
| `views/deployment.png` | L4 Deployment diagram |

## Viewing Diagrams

### PNG exports

Open any `.png` file in the `views/` directory with your image viewer.

### Interactive preview (LikeC4 server)

```bash
npx likec4 start docs/architecture
```

Opens a browser at `http://localhost:5173/` with all views, zoom, pan, and export.

### Exporting

```bash
npx likec4 export png -o docs/architecture/views docs/architecture
```

## Related Documentation

- [Architecture Decision Records](../adr/README.md) — 28 ADRs covering every technology choice
- [Design Specification](../../DESIGN.md) — Full system design (v1.2)
- [Implementation Roadmap](../planning/ROADMAP.md)
- [Project Backlog](../planning/BACKLOG.md)
