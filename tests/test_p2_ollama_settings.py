"""P2 config tests: isolated environment, no credential files or transport."""
from dataclasses import replace
import os
import socket
import urllib.request

import pytest

from app.core.config import (Settings, load_settings, OLLAMA_PRIMARY_MODEL, OLLAMA_PRIMARY_DIGEST,
                             OLLAMA_BACKUP_MODEL, OLLAMA_BACKUP_DIGEST)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setattr(os, "environ", {})

    def forbidden(*args, **kwargs):
        raise AssertionError("transport forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)


def _ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    return load_settings()


def test_mock_defaults_remain_unchanged():
    active = load_settings()
    assert active.llm_provider == "mock" and active.llm_model_name == "mock-rag-guard-v1"


def test_existing_settings_construction_remains_compatible():
    active = Settings("dev", "/tmp/test-audit.jsonl", True, "mock", "mock-rag-guard-v1", 30)
    assert active.ollama_seed == 42 and active.llm_repeat_count == 1


def test_direct_ollama_settings_with_default_mock_model_is_rejected():
    with pytest.raises(ValueError, match="non-mock"):
        Settings("dev", "/tmp/test-audit.jsonl", True, "ollama", "mock-rag-guard-v1", 30)


def test_ollama_defaults_match_frozen_primary_and_backup(monkeypatch):
    active = _ollama(monkeypatch)
    assert (active.llm_model_name, active.ollama_model_digest, active.ollama_model_quantization) == (OLLAMA_PRIMARY_MODEL, OLLAMA_PRIMARY_DIGEST, "Q4_0")
    assert (active.ollama_backup_model_name, active.ollama_backup_model_digest, active.ollama_backup_model_quantization) == (OLLAMA_BACKUP_MODEL, OLLAMA_BACKUP_DIGEST, "Q4_K_M")
    assert active.ollama_expected_version == "0.40.11"
    assert (active.ollama_temperature, active.ollama_seed, active.ollama_num_ctx, active.ollama_num_predict) == (0.0, 42, 4096, 512)
    assert active.ollama_think is False and active.ollama_max_retries == 2 and active.llm_repeat_count == 1


def test_all_declared_ollama_env_overrides_are_loaded(monkeypatch):
    values = {"LLM_PROVIDER": "ollama", "LLM_MODEL_NAME": "synthetic-model", "OLLAMA_MODEL_DIGEST": "1" * 64,
              "OLLAMA_MODEL_QUANTIZATION": "Q8_0", "OLLAMA_BACKUP_MODEL_NAME": "synthetic-backup",
              "OLLAMA_BACKUP_MODEL_DIGEST": "2" * 64, "OLLAMA_BACKUP_MODEL_QUANTIZATION": "F16",
              "OLLAMA_EXPECTED_VERSION": "test-version", "OLLAMA_TEMPERATURE": "0.4", "OLLAMA_SEED": "17",
              "OLLAMA_NUM_CTX": "2048", "OLLAMA_NUM_PREDICT": "64", "LLM_REPEAT_COUNT": "3",
              "OLLAMA_THINK": "yes", "OLLAMA_MAX_RETRIES": "1"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    active = load_settings()
    for key, value in values.items():
        actual = getattr(active, key.lower())
        if key == "OLLAMA_THINK":
            assert actual is True
        elif key == "OLLAMA_TEMPERATURE":
            assert actual == float(value)
        elif key in {"OLLAMA_SEED", "OLLAMA_NUM_CTX", "OLLAMA_NUM_PREDICT", "LLM_REPEAT_COUNT", "OLLAMA_MAX_RETRIES"}:
            assert actual == int(value)
        else:
            assert actual == value


def test_valid_generation_overrides_are_not_rejected_by_config_validation(monkeypatch):
    active = replace(_ollama(monkeypatch), ollama_temperature=0.4, ollama_seed=-9,
                     ollama_num_ctx=2000, ollama_num_predict=7, llm_repeat_count=2)
    assert active.ollama_seed == -9 and active.ollama_temperature == 0.4


def test_backup_selection_uses_backup_identity(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_NAME", OLLAMA_BACKUP_MODEL)
    active = _ollama(monkeypatch)
    assert active.ollama_model_digest == OLLAMA_BACKUP_DIGEST
    assert active.ollama_model_quantization == "Q4_K_M"
    direct = Settings("dev", "/tmp/test.jsonl", True, "ollama", OLLAMA_BACKUP_MODEL, 30)
    assert direct.ollama_model_digest == OLLAMA_BACKUP_DIGEST


def test_unknown_model_does_not_inherit_primary_digest(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_NAME", "synthetic-unknown")
    with pytest.raises(ValueError, match="ollama_model_digest"):
        _ollama(monkeypatch)
    with pytest.raises(ValueError):
        Settings("dev", "/tmp/test.jsonl", True, "ollama", "synthetic-unknown", 30)


@pytest.mark.parametrize("field,value", [
    ("ollama_temperature", True), ("ollama_temperature", float("nan")), ("ollama_temperature", float("inf")),
    ("ollama_temperature", -1), ("ollama_temperature", "0"), ("ollama_seed", True), ("ollama_seed", 1.1),
    ("ollama_num_ctx", True), ("ollama_num_ctx", 0), ("ollama_num_predict", -1), ("ollama_num_predict", 1.5),
    ("llm_repeat_count", 0), ("llm_repeat_count", True), ("ollama_think", "false"),
    ("ollama_model_digest", "A" * 64), ("ollama_model_digest", "a" * 63),
    ("ollama_backup_model_digest", "x" * 64), ("ollama_model_quantization", ""),
    ("ollama_expected_version", " "), ("ollama_max_retries", True), ("ollama_max_retries", 3),
    ("ollama_max_retries", -1), ("llm_model_name", ""), ("llm_model_name", "mock-rag-guard-v1"),
])
def test_invalid_numeric_boolean_digest_and_retry_values_fail(monkeypatch, field, value):
    with pytest.raises(ValueError):
        replace(_ollama(monkeypatch), **{field: value})


@pytest.mark.parametrize("env,value", [("OLLAMA_THINK", "perhaps"), ("OLLAMA_SEED", "true"),
                                       ("OLLAMA_TEMPERATURE", "NaN"), ("OLLAMA_MAX_RETRIES", "2.0")])
def test_invalid_env_values_fail(monkeypatch, env, value):
    monkeypatch.setenv(env, value)
    with pytest.raises(ValueError):
        _ollama(monkeypatch)


def test_ollama_identity_requirements_do_not_break_mock():
    active = replace(load_settings(), ollama_model_digest="invalid", ollama_expected_version="",
                     ollama_model_quantization="", ollama_backup_model_digest="invalid")
    assert active.llm_provider == "mock"


def test_custom_backup_tag_cannot_inherit_known_backup_identity(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BACKUP_MODEL_NAME", "test-only-custom-backup")
    monkeypatch.setenv("LLM_MODEL_NAME", "test-only-custom-backup")
    with pytest.raises(ValueError):
        load_settings()
    monkeypatch.setenv("OLLAMA_BACKUP_MODEL_DIGEST", "9" * 64)
    monkeypatch.setenv("OLLAMA_BACKUP_MODEL_QUANTIZATION", "F16")
    active = load_settings()
    assert active.ollama_model_digest == "9" * 64 and active.ollama_model_quantization == "F16"
