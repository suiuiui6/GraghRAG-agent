"""生产向量门面；兼容准入关闭前默认 fail closed。"""
from sqlite_vector_store import *
from sqlite_vector_store import _build_chroma_metadata, _parse_chroma_metadata

from vector_runtime import SyntheticStorageConfig
