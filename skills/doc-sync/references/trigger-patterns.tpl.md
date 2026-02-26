# Trigger Patterns Reference

Examples of well-formed triggers for {{AGENTS_MD}} index table entries.

## Column Formula

| File         | What                             | When to read                          |
| ------------ | -------------------------------- | ------------------------------------- |
| `[filename]` | [noun-based content description] | [action verb] [specific context/task] |

## Action Verbs by Category

### Implementation Tasks

implementing, adding, creating, building, writing, extending

### Modification Tasks

modifying, updating, changing, refactoring, migrating

### Debugging Tasks

debugging, troubleshooting, investigating, diagnosing, fixing

### Understanding Tasks

understanding, learning, reviewing, analyzing, exploring

## Examples by File Type

### Source Code Files

| File           | What                                | When to read                                                                       |
| -------------- | ----------------------------------- | ---------------------------------------------------------------------------------- |
| `cache.rs`     | LRU cache with O(1) operations      | Implementing caching, debugging cache misses, modifying eviction policy            |
| `auth.rs`      | JWT validation, session management  | Implementing login/logout, modifying token validation, debugging auth failures     |
| `parser.py`    | Input parsing, format detection     | Modifying input parsing, adding new input formats, debugging parse errors          |
| `validator.py` | Validation rules, constraint checks | Adding validation rules, modifying validation logic, understanding validation flow |

### Configuration Files

| File           | What                             | When to read                                                                  |
| -------------- | -------------------------------- | ----------------------------------------------------------------------------- |
| `config.toml`  | Runtime config options, defaults | Adding new config options, modifying defaults, debugging configuration issues |
| `.env.example` | Environment variable template    | Setting up development environment, adding new environment variables          |
| `Cargo.toml`   | Rust dependencies, build config  | Adding dependencies, modifying build configuration, debugging build issues    |

### Test Files

| File                 | What                        | When to read                                                                     |
| -------------------- | --------------------------- | -------------------------------------------------------------------------------- |
| `test_cache.py`      | Cache unit tests            | Adding cache tests, debugging test failures, understanding cache behavior        |
| `integration_tests/` | Cross-component test suites | Adding integration tests, debugging cross-component issues, validating workflows |

### Documentation Files

| File              | What                                     | When to read                                                                             |
| ----------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| `README.md`       | Architecture, design decisions           | Understanding architecture, design decisions, component relationships                    |
| `ARCHITECTURE.md` | System design, component boundaries      | Understanding system design, component boundaries, data flow                             |
| `API.md`          | Endpoint specs, request/response formats | Implementing API endpoints, understanding request/response formats, debugging API issues |

### Index Files (cross-cutting concerns)

| File                      | What                               | When to read                                                                    |
| ------------------------- | ---------------------------------- | ------------------------------------------------------------------------------- |
| `error-handling-index.md` | Error handling patterns reference  | Understanding error handling patterns, failure modes, error recovery strategies |
| `performance-index.md`    | Performance optimization reference | Optimizing latency, throughput, resource usage, understanding cost models       |
| `security-index.md`       | Security patterns reference        | Implementing authentication, encryption, threat mitigation, compliance features |

## Examples by Directory Type

### Feature Directories

| Directory  | What                                    | When to read                                                                          |
| ---------- | --------------------------------------- | ------------------------------------------------------------------------------------- |
| `auth/`    | Authentication, authorization, sessions | Implementing authentication, authorization, session management, debugging auth issues |
| `api/`     | HTTP endpoints, request handling        | Implementing endpoints, modifying request handling, debugging API responses           |
| `storage/` | Persistence, data access layer          | Implementing persistence, modifying data access, debugging storage issues             |

### Layer Directories

| Directory   | What                          | When to read                                                                     |
| ----------- | ----------------------------- | -------------------------------------------------------------------------------- |
| `handlers/` | Request handlers, routing     | Implementing request handlers, modifying routing, debugging request processing   |
| `models/`   | Data models, schemas          | Adding data models, modifying schemas, understanding data structures             |
| `services/` | Business logic, service layer | Implementing business logic, modifying service interactions, debugging workflows |

### Utility Directories

| Directory  | What                              | When to read                                                                       |
| ---------- | --------------------------------- | ---------------------------------------------------------------------------------- |
| `utils/`   | Helper functions, common patterns | Needing helper functions, implementing common patterns, debugging utility behavior |
| `scripts/` | Maintenance tasks, automation     | Running maintenance tasks, automating workflows, debugging script execution        |
| `tools/`   | Development tools, CLI utilities  | Using development tools, implementing tooling, debugging tool behavior             |

## Anti-Patterns

### Too Vague (matches everything)

| File       | What          | When to read               |
| ---------- | ------------- | -------------------------- |
| `config/`  | Configuration | Working with configuration |
| `utils.py` | Utilities     | When you need utilities    |

### Content Description Only (no trigger)

| File       | What                                          | When to read |
| ---------- | --------------------------------------------- | ------------ |
| `cache.rs` | Contains the LRU cache implementation         | -            |
| `auth.rs`  | Authentication logic including JWT validation | -            |

### Missing Action Verb

| File           | What             | When to read                      |
| -------------- | ---------------- | --------------------------------- |
| `parser.py`    | Input parsing    | Input parsing and format handling |
| `validator.py` | Validation rules | Validation rules and constraints  |

## Trigger Guidelines

- Combine 2-4 triggers per entry using commas or "or"
- Use action verbs: implementing, debugging, modifying, adding, understanding
- Be specific: "debugging cache misses" not "debugging"
- If more than 4 triggers needed, the file may be doing too much
