"""Synthetic software cases plus a read-only real SQLite schema check."""
import importlib
from pathlib import Path

import pytest

from backend.tests.frozen_input_helpers import CODE_ROOT as ROOT, current_module, frozen_gold, frozen_database


def tool():
    assert (ROOT / 'backend/research/source_mapping_v2.py').exists(), 'mapping tool not implemented'
    return current_module('source_mapping_v2')


def test_exact_unique_non_bmp_mapping():
    r = tool().map_text('甲\r\n😀XYZ', '😀X', (2, 4))
    assert r == {'status': 'EXACT_STORED_SPAN', 'stored_span_verified': True,
                 'candidates': [[2, 4]], 'resolved_span': [2, 4]}


def test_bad_coordinate_not_silently_repaired():
    r = tool().map_text('prefix target tail', 'target', (6, 12))
    assert r['status'] == 'UNIQUE_TEXT_MATCH_STORED_SPAN_INVALID'
    assert not r['stored_span_verified'] and r['resolved_span'] is None
    assert r['candidates'] == [[7, 13]]


def test_repeated_text_requires_verified_coordinate():
    m = tool()
    assert m.map_text('abc abc', 'abc')['status'] == 'AMBIGUOUS_TEXT_MATCH'
    assert m.map_text('abc abc', 'abc', (4, 7))['status'] == 'EXACT_STORED_SPAN'


def test_missing_or_empty_text_is_not_absence_evidence():
    assert tool().map_text('text', '')['status'] == 'LOCATION_UNVERIFIED'
    assert tool().map_text('text', 'transformed')['status'] == 'LOCATION_UNVERIFIED'


@pytest.mark.parametrize('span', [(True, 3), (-1, 3), (0, 99), (0, 2.5)])
def test_invalid_coordinate_is_not_verified(span):
    assert not tool().map_text('abc', 'abc', span)['stored_span_verified']


def test_read_only_real_sqlite_and_privacy(monkeypatch):
    m = tool()
    opened = []
    connect = m.sqlite3.connect
    def record_readonly(*args, **kwargs):
        opened.append((args[0], kwargs.get('uri')))
        return connect(*args, **kwargs)
    monkeypatch.setattr(m.sqlite3, 'connect', record_readonly)
    texts = {'D1': frozen_gold().texts['D1']}
    with frozen_database() as database:
        report = m.audit_chroma(database, texts)
    assert opened and all(uri.endswith('?mode=ro') and enabled is True for uri, enabled in opened)
    assert report['hashes_before'] == report['hashes_after']
    assert report['database_unchanged']
    assert report['status'] == 'READ_ONLY_SNAPSHOT_AUDIT'
    assert report['runtime_membership'] == 'UNKNOWN'
    assert report['collections'] and report['chunk_records'] > 0
    assert 'text' not in str(report['sources']['D1'].keys())
    assert report['sources']['D1']['exact_substring_chunks'] > 0
    assert report['sources']['D1']['stored_span_verified_chunks'] < report['sources']['D1']['exact_substring_chunks']
