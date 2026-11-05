# NATS JetStream Sequence Discrepancy Explanation

**Scope**: Round 4 Target 2 — Technical breakdown of sequence numbers in NATS JetStream telemetry streams.

---

## 1. Sequence Terminology Definitions

| Term | Scope | Description |
| :--- | :--- | :--- |
| **Stream Sequence (`Stream.Sequence`)** | Stream Storage | Monotonically increasing 64-bit integer assigned by JetStream Raft engine to every message written to `telemetry_stream_critical`. |
| **Consumer Sequence (`Consumer.Sequence`)** | Consumer Group | Consumer-specific cursor tracking how many messages this specific consumer has fetched. |
| **Delivered Sequence (`Delivered.StreamSequence`)** | Network Transport | The Stream Sequence ID delivered over the socket to an active subscriber. |
| **Acked Sequence (`Acked.StreamSequence`)** | State Checkpoint | The Stream Sequence ID explicitly acknowledged (`msg.ack()`) by the consumer back to JetStream. |

---

## 2. Sequence Lifecycle in Disconnect & Recovery Test

```text
1. Active Consumer Subscribed => Reads backlog starting at Stream Sequence 26632
2. JetStream Publish while online => Stream Sequence 26668 assigned & ACKed
3. Consumer Disconnected (Offline State)
4. JetStream Publish while offline => Stream Sequence 26669 written to disk log
5. Consumer Reconnected => Fetches unacknowledged backlog starting at Stream Sequence 26669
6. Consumer issues msg.ack() => JetStream updates durable checkpoint to Sequence 26669
```

- **Verdict**: **CLOSED (EXPLAINED)** — Sequence mechanics verified. Stream Sequence 26669 was persisted on disk while consumer was offline and replayed cleanly upon reconnect with zero message loss.
