from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List


@dataclass
class RepositoryManifest:
    name: str
    archive_path: str
    wiki_archive_path: str = ""
    backup_status: str = "success"
    metadata_counts: Dict[str, int] = field(default_factory=dict)
    error: str = ""


@dataclass
class Manifest:
    started_at: datetime
    completed_at: datetime
    retention_days: int
    repositories: List[RepositoryManifest]
    organization_exports: Dict[str, int]
    errors: List[str] = field(default_factory=list)
    schema_version: str = "1.0.0"

    def to_dict(self) -> Dict:
        return {
            "schema_version": self.schema_version,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "retention_days": self.retention_days,
            "repositories": [dataclasses.asdict(repo) for repo in self.repositories],
            "organization_exports": self.organization_exports,
            "errors": self.errors,
        }

    def write(self, path: Path) -> None:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
