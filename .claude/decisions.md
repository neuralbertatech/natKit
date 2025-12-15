# Decision Log

> Lightweight record of architectural decisions. For full context and queryable history, see graphiti-memory.

## Template

```
### [YYYY-MM-DD] Decision Title

**Context:** Why this decision was needed

**Decision:** What was decided

**Alternatives considered:** What else was evaluated

**Consequences:** What this means going forward
```

---

## Decisions

<!-- Add decisions below, newest first -->

### [2025-12-13] Kafka Consumer Start Offset

**Context:** Stream Viewer was reading from the beginning of Kafka topics, causing delay before showing live data

**Decision:** Changed default `startOffset` from `0` to `-1` (RD_KAFKA_OFFSET_END) in BrokerMessagingQueue

**Alternatives considered:** Could have added a parameter to createMessenger() to allow caller to specify, but all current use cases want latest data

**Consequences:** All Kafka consumers now start from the latest message by default. If historical data is needed, callers must explicitly pass a different offset.

---

### [2025-12-13] Drogon WebSocket Controller Registration

**Context:** WebSocket endpoint `/ws/stream_viewer` was returning 404 despite code being present

**Decision:** Manually register WebSocket controller with `app().registerController()` since it uses `AutoCreation=false`

**Alternatives considered:** Could have changed to `AutoCreation=true`, but that would prevent setting the broker manager before registration

**Consequences:** Must remember to manually register any controllers that use `AutoCreation=false`. The `WS_PATH_ADD` macro alone is not sufficient.
