# ADR-0001: Record Architecture Decisions

## Status
Accepted

## Context
We need to maintain a clear architectural structure for Sofia V2 to ensure:
- Clear separation of concerns between UI, API, and services
- Single source of truth for market symbols and configuration
- Consistent data flow patterns
- Maintainable and testable codebase

## Decision
We will adopt a layered architecture with the following structure:
- `src/api/` - HTTP interface layer (FastAPI routes)
- `src/services/` - Business logic and domain services
- `src/domain/` - Domain models and entities
- `src/adapters/` - External integrations (exchanges, databases)
- `src/ui/` - Web interface templates and static assets

Import rules:
- API can import from services and domain
- Services can import from domain and adapters
- Domain has no external dependencies
- Adapters can only import from domain

## Consequences

### Positive
- Easier maintenance through clear boundaries
- Less code duplication
- Clear ownership and responsibilities
- Better testability with dependency injection
- Easier to onboard new developers

### Negative
- Initial setup complexity
- Need to enforce import rules
- May require refactoring existing code

## References
- Clean Architecture by Robert C. Martin
- Domain-Driven Design by Eric Evans
