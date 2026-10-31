"""Explicit offline-model dependency preparation inside coverage, before collection.

This imports a trusted library only. Model bytes, model identity, HTTP behavior
and process restart assertions remain in the actual tests with their budgets.
Run this file via coverage run with the normal pytest arguments.
"""
import importlib
import os
import runpy
import time

started = time.monotonic()
if os.environ.get('GRAPHRAG_TEST_MODEL_RECEIPT'):
    importlib.import_module('sentence_transformers')
    print('MODEL_LIBRARY_PREPARATION_SECONDS=' + format(time.monotonic() - started, '.3f'), flush=True)
runpy.run_module('pytest', run_name='__main__')
