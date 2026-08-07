import json
from pathlib import Path

from app.workspace import routes, store


def test_admin_stats_exposes_safe_stage_details(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    monkeypatch.chdir(tmp_path)
    store.initialize()
    admin = next(user for user in store.users() if user["username"] == "superadmin")

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    event = {
        "timestamp": "2026-08-06T09:49:12+00:00",
        "request_id": "request-123",
        "endpoint": "/v1/gateway/chat",
        "input_preview": "Ignore previous instructions [REDACTED]",
        "input_decision": {
            "decision": "block",
            "risk_score": 0.95,
            "matched_rules": ["prompt_injection"],
        },
        "rag_decision": {
            "decision": "allow",
            "risk_score": 0.0,
            "matched_rules": [],
        },
        "final_decision": "block",
        "reasons": ["Input guard blocked the request"],
        "metadata": {
            "workspace_user_id": 3,
            "role": "member",
            "department": "IT",
            "workspace_directory": "must never be returned by admin stats",
        },
        "provider": {
            "provider_name": "ollama",
            "model_name": "qwen3:4b-instruct",
            "is_mock": False,
        },
    }
    safe_event = {
        **event,
        "request_id": "request-safe",
        "final_decision": "allow",
        "input_decision": {
            "decision": "allow",
            "risk_score": 0.0,
            "matched_rules": [],
        },
    }
    (log_dir / "audit.jsonl").write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False) for item in (event, safe_event)
        )
        + "\n",
        encoding="utf-8",
    )

    result = routes.admin_stats(admin)
    recent = result["audit"]["recent"][0]

    assert result["audit"]["decisions"] == {"block": 1, "allow": 1}
    assert result["audit"]["dangerous_total"] == 1
    assert len(result["audit"]["recent"]) == 1
    assert recent["endpoint"] == "/v1/gateway/chat"
    assert recent["input_preview"].endswith("[REDACTED]")
    assert recent["matched_rules"] == ["prompt_injection"]
    assert recent["stages"]["input"] == {
        "decision": "block",
        "risk_score": 0.95,
        "matched_rules": ["prompt_injection"],
    }
    assert recent["actor"] == {"user_id": 3, "role": "member", "department": "IT"}
    assert recent["provider"]["model"] == "qwen3:4b-instruct"
    assert "workspace_directory" not in recent
