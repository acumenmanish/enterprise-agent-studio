import re
import subprocess
from pathlib import Path, PurePosixPath


class ManifestRepositoryError(RuntimeError):
    pass


class LocalManifestRepository:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self, tenant_id: str, agent_id: str, initial_yaml: str) -> str:
        manifest_path = self._manifest_path(tenant_id, agent_id)
        self.path.mkdir(parents=True, exist_ok=True)
        if not (self.path / ".git").exists():
            self._run("init")
        self._run("config", "user.name", "Enterprise Agent Studio")
        self._run("config", "user.email", "agent-studio@localhost")

        destination = self.path / manifest_path
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(initial_yaml, encoding="utf-8")
            self._run("add", "--", manifest_path.as_posix())
            self._run("commit", "-m", "Initialize agent manifest", "--", manifest_path.as_posix())
        return destination.read_text(encoding="utf-8")

    def read(self, tenant_id: str, agent_id: str) -> str:
        path = self.path / self._manifest_path(tenant_id, agent_id)
        if not path.is_file():
            raise ManifestRepositoryError("Agent manifest is missing from the local repository")
        return path.read_text(encoding="utf-8")

    def commit(
        self,
        tenant_id: str,
        agent_id: str,
        manifest_yaml: str,
        message: str,
    ) -> str:
        manifest_path = self._manifest_path(tenant_id, agent_id)
        destination = self.path / manifest_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(manifest_yaml, encoding="utf-8")
        self._run("add", "--", manifest_path.as_posix())
        self._run(
            "commit",
            "--only",
            "-m",
            message,
            "--",
            manifest_path.as_posix(),
        )
        return self._run("rev-parse", "HEAD")

    def history(self, tenant_id: str, agent_id: str, limit: int = 50) -> list[dict[str, str]]:
        manifest_path = self._manifest_path(tenant_id, agent_id)
        output = self._run(
            "log",
            f"-{limit}",
            "--format=%H%x1f%aI%x1f%s",
            "--",
            manifest_path.as_posix(),
        )
        revisions = []
        for line in output.splitlines():
            commit, created_at, message = line.split("\x1f", maxsplit=2)
            revisions.append(
                {"commit": commit, "created_at": created_at, "message": message}
            )
        return revisions

    def read_revision(
        self, tenant_id: str, agent_id: str, commit: str
    ) -> str:
        manifest_path = self._manifest_path(tenant_id, agent_id)
        self._validate_commit(commit)
        return self._run("show", f"{commit}:{manifest_path.as_posix()}")

    def compare(
        self, tenant_id: str, agent_id: str, from_commit: str, to_commit: str
    ) -> str:
        manifest_path = self._manifest_path(tenant_id, agent_id)
        self._validate_commit(from_commit)
        self._validate_commit(to_commit)
        return self._run(
            "diff",
            "--no-ext-diff",
            "--unified=3",
            from_commit,
            to_commit,
            "--",
            manifest_path.as_posix(),
        )

    def _run(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.path), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = result.stderr.strip() or "unknown git error"
            raise ManifestRepositoryError(f"Local agent repository operation failed: {detail}")
        return result.stdout.strip()

    @staticmethod
    def _manifest_path(tenant_id: str, agent_id: str) -> PurePosixPath:
        safe_segment = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
        if not safe_segment.fullmatch(tenant_id) or not safe_segment.fullmatch(agent_id):
            raise ManifestRepositoryError("Tenant and agent identifiers must be safe path segments")
        return PurePosixPath("tenants", tenant_id, "agents", agent_id, "manifest.yaml")

    @staticmethod
    def _validate_commit(commit: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ManifestRepositoryError("Invalid local agent revision")
