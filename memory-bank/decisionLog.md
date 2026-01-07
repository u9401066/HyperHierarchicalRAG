# Decision Log

## 2026-01-06: Project Scaffolded
- **Decision**: Used `u9401066/template-is-all-you-need` as the base.
- **Rationale**: Provides solid Constitution-Bylaw-Skill structure and Memory Bank pattern.
| 2026-01-07 | Dual-Path Storage Architecture (Enterprise vs. Local-Fast SQLite) | To provide immediate local usability with zero-config (SQLite) while maintaining a high-performance path for enterprise scale (Milvus/PostgreSQL). SQLite allows for transactionally consistent storage of KG, Memory, and Metadata in a single file for better reliability and performance at scale. |
