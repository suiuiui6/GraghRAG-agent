"""SQLite 安全运行库探针与显式合成数据准入。无环境变量绕过。"""
from __future__ import annotations
from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from vector_errors import VectorStorageError

MIN_SQLITE_VERSION = (3, 53, 2)
HARDENING_OPTIONS = tuple((getattr(sqlite3, name, None), enabled) for name, enabled in (
    ('SQLITE_DBCONFIG_DEFENSIVE', True),
    ('SQLITE_DBCONFIG_TRUSTED_SCHEMA', False),
    ('SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION', False),
))
_MARKER = '.synthetic-vector-integration.json'
_PURPOSE = {'purpose': 'vector-production-integration-synthetic-only', 'version': 1}

@dataclass(frozen=True)
class SyntheticIntegrationConfig:
    """专用合成夹具目录的显式能力，不得用于生产资料迁移。"""
    fixture_root: Path

    @classmethod
    def create(cls, fixture_root):
        root = Path(fixture_root)
        _validate_root(root)
        root = root.resolve()
        marker = root / _MARKER
        if not marker.exists():
            if root.exists() and any(root.iterdir()):
                raise VectorStorageError('compatibility_not_approved', 'open')
            root.mkdir(parents=True, exist_ok=True)
            with marker.open('x', encoding='utf-8') as stream:
                json.dump(_PURPOSE, stream, sort_keys=True)
        config = cls(root)
        require_admission(root, config)
        return config

def _validate_root(root):
    production = (Path(__file__).parent / 'output').resolve()
    if not root.is_absolute():
        raise VectorStorageError('compatibility_not_approved', 'open')
    resolved = root.resolve()
    if resolved.is_relative_to(production) or production.is_relative_to(resolved):
        raise VectorStorageError('compatibility_not_approved', 'open')

def require_admission(persist_dir, config):
    path=Path(persist_dir).resolve()
    if (path/'chroma.sqlite3').exists() and not (path/'vectors.sqlite').exists():
        raise VectorStorageError('migration_required','open')
    if type(config) is SyntheticStorageConfig:
        config._validate()
        path=Path(persist_dir).resolve()
        if path != config.root and config.root not in path.parents:
            raise VectorStorageError('compatibility_not_approved','open')
        return
    if type(config) is not SyntheticIntegrationConfig:
        raise VectorStorageError('compatibility_not_approved', 'open')
    root = config.fixture_root
    _validate_root(root)
    path = Path(persist_dir).resolve()
    if not path.is_relative_to(root.resolve()):
        raise VectorStorageError('compatibility_not_approved', 'open')
    try:
        if json.loads((root / _MARKER).read_text(encoding='utf-8')) != _PURPOSE:
            raise ValueError('invalid marker')
    except (OSError, ValueError, TypeError) as exc:
        raise VectorStorageError('compatibility_not_approved', 'open') from exc

def _harden(connection):
    try:
        for option, enabled in HARDENING_OPTIONS:
            if option is None:
                raise RuntimeError('missing runtime option')
            connection.setconfig(option, enabled)
            if connection.getconfig(option) != enabled:
                raise RuntimeError('runtime option not applied')
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        if connection.execute('PRAGMA foreign_keys').fetchone() != (1,):
            raise RuntimeError('foreign key enforcement unavailable')
        if connection.execute('PRAGMA trusted_schema').fetchone() != (0,):
            raise RuntimeError('trusted schema remains enabled')
    except Exception as exc:
        raise VectorStorageError('runtime_hardening_failed', 'open') from exc

def probe_runtime():
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        raise VectorStorageError('runtime_unsupported', 'open')
    with closing(sqlite3.connect(':memory:')) as connection:
        _harden(connection)
    return {'sqlite_version': sqlite3.sqlite_version, 'hardening': True}

def connect(path, ro=False):
    """每个连接单独硬化；ro 从不创建空库。调用者负责 close。"""
    probe_runtime()
    connection = sqlite3.connect(Path(path).resolve().as_uri() + ('?mode=ro' if ro else '?mode=rwc'), uri=True, timeout=.5)
    try:
        _harden(connection)
        return connection
    except BaseException:
        connection.close()
        raise

import tempfile
import shutil
_CANDIDATE_MARKER = '.graphrag-synthetic.json'
_CANDIDATE_CONTENT = {'format': 1, 'purpose': 'synthetic-vector-integration'}

class SyntheticStorageConfig:
    """Explicit test admission for an exclusively allocated OS temporary root.

    create() allocates an empty directory; from_root() reopens its marker in a
    child process. There is no general compatibility override or production flag.
    """
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._validate()

    @classmethod
    def create(cls):
        root = Path(tempfile.mkdtemp(prefix='graphrag-synthetic-'))
        try:
            (root / _CANDIDATE_MARKER).write_text(json.dumps(_CANDIDATE_CONTENT), encoding='utf-8')
            return cls(root)
        except BaseException:
            shutil.rmtree(root)
            raise

    @classmethod
    def from_root(cls, root):
        return cls(root)

    def _validate(self):
        root = self.root
        temp_root = Path(tempfile.gettempdir()).resolve()
        marker = root / _CANDIDATE_MARKER
        try:
            valid = (root.parent == temp_root
                     and root.name.startswith('graphrag-synthetic-')
                     and not root.is_symlink() and not marker.is_symlink()
                     and marker.stat().st_size < 256
                     and json.loads(marker.read_text(encoding='utf-8')) == _CANDIDATE_CONTENT)
        except (OSError, ValueError):
            valid = False
        if not valid:
            raise VectorStorageError('compatibility_not_approved', 'open')

    def __enter__(self):
        self._validate()
        return self

    def __exit__(self, *exc):
        self._validate()
        shutil.rmtree(self.root)


validate_runtime = probe_runtime
authorize_storage = require_admission
