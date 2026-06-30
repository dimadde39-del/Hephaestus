# TTL cache

`TTLCache(ttl, clock=time.monotonic)` exposes `set`, `get`, membership, and
`len`. The optional clock makes time-dependent behavior deterministic in tests.

