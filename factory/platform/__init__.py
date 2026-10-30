"""The data platform as the agents see it: gold tables (read), the files bucket
(read by pointer and hash), the agent's evidence bucket (write) and its outcomes
dataset (write). Nothing here reaches bronze, silver, the landing bucket or a
source system; the write path to SAP and Salesforce is a Gate 2 decision and lives
behind the agents' connector protocols, not here."""

from .evidence import (
    JSON,
    EvidenceStore,
    GcsEvidenceStore,
    InMemoryEvidenceStore,
    LocalEvidenceStore,
)
from .files import (
    FileError,
    FileStore,
    GcsFileStore,
    InMemoryFileStore,
    IntegrityError,
    LocalFileStore,
    fetch_verified,
    sha256_hex,
)
from .gold import (
    BigQueryGoldClient,
    Freshness,
    GoldClient,
    GoldError,
    GoldReader,
    GoldStale,
    InMemoryGoldClient,
    Lookup,
    UnknownColumn,
    refresh_snapshot,
)
from .outcomes import (
    BigQueryOutcomeSink,
    InMemoryOutcomeSink,
    OutcomeSink,
    OutcomeWriteFailed,
    base_row,
    json_text,
)
from .schema import GOLD, REFRESH, GoldRegistry, GoldTable, UnknownTable

__all__ = [
    "GOLD",
    "JSON",
    "REFRESH",
    "BigQueryGoldClient",
    "BigQueryOutcomeSink",
    "EvidenceStore",
    "FileError",
    "FileStore",
    "Freshness",
    "GcsEvidenceStore",
    "GcsFileStore",
    "GoldClient",
    "GoldError",
    "GoldReader",
    "GoldRegistry",
    "GoldStale",
    "GoldTable",
    "InMemoryEvidenceStore",
    "InMemoryFileStore",
    "InMemoryGoldClient",
    "InMemoryOutcomeSink",
    "IntegrityError",
    "LocalEvidenceStore",
    "LocalFileStore",
    "Lookup",
    "OutcomeSink",
    "OutcomeWriteFailed",
    "UnknownColumn",
    "UnknownTable",
    "base_row",
    "fetch_verified",
    "json_text",
    "refresh_snapshot",
    "sha256_hex",
]
