import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.conversation import (
    ConversationMemoryCandidate,
    ConversationMemoryUpdate,
    ConversationRepository,
    ConversationRequest,
    ConversationService,
    DeliberationMode,
)
from hephaestus.memory import MemoryType
from hephaestus.release import ReleasePlanningOrchestrator, ReleasePlanningRequest
from hephaestus.repo.repository import RepoProfileRepository
from hephaestus.repo.schemas import RepoProfile
from hephaestus.studio.app import create_studio_app
from hephaestus.studio.repository import EMPTY_CONVERSATION_TITLE
from hephaestus.studio.schemas import CreateConversationRequest
from hephaestus.studio.security import (
    DEFAULT_STUDIO_HOST,
    DEFAULT_STUDIO_PORT,
    is_loopback_host,
    resolve_static_dir,
    studio_url,
)
from hephaestus.studio.services import StudioService
from hephaestus.tool_runtime import ShellCommandRequest, ToolRuntime

runner = CliRunner()


def _client(database_path: Path) -> TestClient:
    return TestClient(create_studio_app(database_path))


def test_studio_health_and_config_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("HEPH_OPENAI_COMPAT_BASE_URL", raising=False)
    monkeypatch.delenv("HEPH_OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.delenv("HEPH_OPENAI_COMPAT_MODEL", raising=False)
    client = _client(tmp_path / "hephaestus.db")

    health = client.get("/api/health")
    config = client.get("/api/config")

    assert health.status_code == 200
    assert health.json()["provider_label"] == "Local deterministic mode"
    assert config.status_code == 200
    assert config.json()["default_url"] == "http://127.0.0.1:8741"


def test_studio_static_export_serves_deep_links(tmp_path) -> None:
    static_dir = tmp_path / "out"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>Studio app shell</main>", encoding="utf-8")
    (static_dir / "404.html").write_text("<main>Static 404</main>", encoding="utf-8")
    client = TestClient(create_studio_app(tmp_path / "hephaestus.db", static_dir=static_dir))

    response = client.get("/conversations/demo-session")

    assert response.status_code == 200
    assert "Studio app shell" in response.text
    assert "Static 404" not in response.text


def test_conversation_create_title_message_order_and_reopen(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    client = _client(database_path)

    created = client.post("/api/conversations", json={"mode": "strategic"})
    session_id = created.json()["id"]
    prompt = "Stress-test Hephaestus launch without automatic recaps."
    posted = client.post(
        f"/api/conversations/{session_id}/messages",
        json={"content": prompt, "mode": "strategic", "provider": "local"},
    )
    reopened_client = _client(database_path)
    reopened = reopened_client.get(f"/api/conversations/{session_id}/messages")
    detail = reopened_client.get(f"/api/conversations/{session_id}")

    assert created.status_code == 201
    assert created.json()["title"] == EMPTY_CONVERSATION_TITLE
    assert posted.status_code == 200
    assert posted.json()["conversation"]["title"] == prompt
    assert [message["role"] for message in posted.json()["messages"]] == ["user", "assistant"]
    assert posted.json()["messages"][0]["content"] == prompt
    assert reopened.status_code == 200
    assert reopened.json() == posted.json()["messages"]
    assert detail.status_code == 200
    assert len(reopened.json()) == 2


def test_rename_pin_archive_and_sidebar_sorting(tmp_path) -> None:
    client = _client(tmp_path / "hephaestus.db")
    first_id = client.post("/api/conversations", json={"title": "Recent work"}).json()["id"]
    second_id = client.post("/api/conversations", json={"title": "Pinned work"}).json()["id"]

    rename = client.patch(
        f"/api/conversations/{first_id}",
        json={"title": "README positioning versus Hermes"},
    )
    pin = client.post(f"/api/conversations/{second_id}/pin", json={"is_pinned": True})
    archive = client.post(f"/api/conversations/{first_id}/archive", json={"is_archived": True})
    active_list = client.get("/api/conversations")
    archived_list = client.get("/api/conversations?archived_only=true")

    assert rename.status_code == 200
    assert rename.json()["title"] == "README positioning versus Hermes"
    assert pin.status_code == 200
    assert pin.json()["is_pinned"] is True
    assert archive.status_code == 200
    assert archive.json()["is_archived"] is True
    assert active_list.json()["conversations"][0]["id"] == second_id
    assert [item["id"] for item in archived_list.json()["conversations"]] == [first_id]


def test_search_user_and_agent_messages(tmp_path) -> None:
    client = _client(tmp_path / "hephaestus.db")
    session_id = client.post("/api/conversations", json={}).json()["id"]
    client.post(
        f"/api/conversations/{session_id}/messages",
        json={
            "content": "Plan a validation-backed coding loop for Studio search.",
            "provider": "local",
        },
    )

    user_search = client.get("/api/search?q=validation-backed")
    agent_search = client.get("/api/search?q=Provider%20note")

    assert user_search.status_code == 200
    assert any(result["role"] == "user" for result in user_search.json()["results"])
    assert agent_search.status_code == 200
    assert any(result["role"] == "assistant" for result in agent_search.json()["results"])


def test_mode_repo_context_and_provider_policy_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    database_path = tmp_path / "hephaestus.db"
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    profile = RepoProfileRepository(database_path).save_profile(
        RepoProfile(
            path=str(repo_path.resolve()),
            name="Fixture Repo",
            detected_languages=["Python"],
        )
    )
    client = _client(database_path)
    session_id = client.post(
        "/api/conversations",
        json={"mode": "architect", "repo_profile_id": profile.id},
    ).json()["id"]

    detail = client.get(f"/api/conversations/{session_id}")
    modes = client.get("/api/modes")
    policy = client.get("/api/policy/active")
    providers = client.get("/api/providers/status")
    repos = client.get("/api/repos/recent")

    assert detail.json()["conversation"]["mode"] == "architect"
    assert detail.json()["conversation"]["repo_profile_id"] == profile.id
    assert any(mode["value"] == "skeptical_but_fair" for mode in modes.json())
    assert policy.json()["profile_type"] == "balanced"
    assert providers.json()["active_label"] == "Local deterministic mode"
    assert repos.json()[0]["id"] == profile.id


def test_posting_message_uses_local_provider_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("HEPH_OPENAI_COMPAT_BASE_URL", raising=False)
    monkeypatch.delenv("HEPH_OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.delenv("HEPH_OPENAI_COMPAT_MODEL", raising=False)
    client = _client(tmp_path / "hephaestus.db")
    session_id = client.post("/api/conversations", json={}).json()["id"]

    posted = client.post(
        f"/api/conversations/{session_id}/messages",
        json={"content": "What is Hephaestus Studio?", "provider": "auto"},
    )

    assert posted.status_code == 200
    assert posted.json()["provider_model"].startswith("local/")
    assert "Provider note" in posted.json()["messages"][-1]["content"]


def test_existing_cli_sessions_visible_in_studio_and_back(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    cli_response = ConversationService(database_path).respond(
        ConversationRequest(
            prompt="README positioning versus Hermes",
            mode=DeliberationMode.STRATEGIC,
            provider="local",
        )
    )
    studio = StudioService(database_path)

    conversations = studio.list_conversations().conversations
    studio_session = studio.create_conversation(
        request=CreateConversationRequest(title="Studio-created session")
    )
    cli_readback = ConversationService(database_path).get_session(studio_session.id)

    assert any(conversation.id == cli_response.session_id for conversation in conversations)
    assert cli_readback is not None
    assert cli_readback.title == "Studio-created session"


def test_no_automatic_summary_generation_on_reopen(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    client = _client(database_path)
    session_id = client.post("/api/conversations", json={}).json()["id"]
    client.post(
        f"/api/conversations/{session_id}/messages",
        json={"content": "Continue tomorrow without a recap.", "provider": "local"},
    )
    before = client.get(f"/api/conversations/{session_id}/messages").json()
    detail = client.get(f"/api/conversations/{session_id}")
    after = client.get(f"/api/conversations/{session_id}/messages").json()
    session = ConversationService(database_path).get_session(session_id)

    assert detail.status_code == 200
    assert before == after
    assert session is not None
    assert session.summary == ""


def test_studio_cli_doctor_and_localhost_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["studio", "doctor"])

    assert result.exit_code == 0
    assert "Hephaestus Studio Doctor" in result.output
    assert studio_url(DEFAULT_STUDIO_HOST, DEFAULT_STUDIO_PORT) == "http://127.0.0.1:8741"
    assert is_loopback_host(DEFAULT_STUDIO_HOST)


def test_workbench_coding_diff_checkpoint_restore_and_linked_conversation(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repo = _workbench_repo(tmp_path)
    client = _client(database_path)
    session_id = client.post(
        "/api/conversations",
        json={"title": "Workbench linked chat", "workspace_path": str(repo)},
    ).json()["id"]

    trust = client.patch(
        "/api/trust",
        json={"mode": "manual", "rules": {"apply_low_risk_documentation_patches": False}},
    )
    proposed = client.post(
        "/api/coding/propose",
        json={
            "user_request": "Update README intro to mention validation-backed release evidence.",
            "repo_path": str(repo),
            "conversation_id": session_id,
        },
    )
    coding_id = proposed.json()["summary"]["id"]
    change_id = proposed.json()["changes"][0]["id"]
    unapproved = client.post(f"/api/coding/{change_id}/apply", json={"approved": False})
    approved = client.post(
        f"/api/coding/{change_id}/apply",
        json={"approved": True, "no_validate": True},
    )
    checkpoint_id = approved.json()["summary"]["checkpoint_state"]
    detail = client.get(f"/api/coding/{coding_id}")
    coding_list = client.get(f"/api/coding?conversation={session_id}")
    overview = client.get("/api/workbench/overview")

    assert trust.status_code == 200
    assert proposed.status_code == 200
    assert "validation-backed release evidence" in proposed.json()["changes"][0]["diff"].lower()
    assert unapproved.status_code == 200
    assert unapproved.json()["summary"]["status"]["value"] == "requires_approval"
    assert approved.status_code == 200
    assert approved.json()["summary"]["status"]["value"] == "completed"
    assert checkpoint_id == "available"
    assert detail.json()["linked_conversation"]["href"] == f"/conversations/{session_id}"
    assert coding_list.json()["items"][0]["conversation_id"] == session_id
    assert overview.json()["recent_checkpoints"]

    checkpoint_summary = overview.json()["recent_checkpoints"][0]
    checkpoint_detail = client.get(checkpoint_summary["href"].replace("/workbench", "/api"))
    (repo / "README.md").write_text("manual later edit\n", encoding="utf-8")
    restore_pending = client.post(
        f"/api/checkpoints/{checkpoint_summary['id']}/restore",
        json={"approved": False},
    )
    assert (repo / "README.md").read_text(encoding="utf-8") == "manual later edit\n"
    restored = client.post(
        f"/api/checkpoints/{checkpoint_summary['id']}/restore",
        json={"approved": True},
    )

    assert checkpoint_detail.status_code == 200
    assert checkpoint_detail.json()["summary"]["files_covered"] == ["README.md"]
    assert restore_pending.status_code == 200
    assert restored.status_code == 200
    assert (repo / "README.md").read_text(encoding="utf-8").startswith(
        "Hephaestus is a self-improving AI agent."
    )


def test_workbench_validation_tools_redaction_and_destructive_blocking(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repo = _workbench_repo(tmp_path)
    client = _client(database_path)

    plan = client.post("/api/validation/plan", json={"repo_path": str(repo)})
    run = client.post(
        "/api/validation/run",
        json={"repo_path": str(repo), "approved": True},
    )
    runtime = ToolRuntime(database_path, workspace_path=repo)
    _secret_plan, secret_action, _secret_result = runtime.run_command(
        ShellCommandRequest(
            command='python -c "print(\'SECRET_TOKEN=supersecret123\')"',
            yes=True,
        )
    )
    _blocked_plan, blocked_action, blocked_result = runtime.run_command(
        ShellCommandRequest(command="rm -rf dist", yes=True)
    )
    actions = client.get("/api/tools/actions")
    secret_detail = client.get(f"/api/tools/actions/{secret_action.id}")
    blocked_detail = client.get(f"/api/tools/actions/{blocked_action.id}")

    assert plan.status_code == 200
    assert plan.json()["commands"]
    assert run.status_code == 200
    assert run.json()["summary"]["status"]["value"] == "passed"
    assert run.json()["commands"][0]["tool_action_id"] is not None
    assert actions.status_code == 200
    assert "supersecret123" not in secret_detail.text
    assert "[redacted]" in secret_detail.text
    assert blocked_result.status.value == "blocked"
    assert blocked_detail.json()["summary"]["status"]["value"] == "blocked"


def test_workbench_release_outcome_and_trust_persistence(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repo = _workbench_repo(tmp_path)
    client = _client(database_path)
    demo = ReleasePlanningOrchestrator(database_path).plan(
        ReleasePlanningRequest(path=str(repo), pareto=True, qubo=True, evaluate=True)
    )

    updated_trust = client.patch(
        "/api/trust",
        json={
            "mode": "local_power_user",
            "rules": {
                "apply_low_risk_code_patches_with_validation": True,
                "push_git_changes": True,
            },
        },
    )
    reopened = _client(database_path)
    trust = reopened.get("/api/trust")
    releases = reopened.get("/api/releases")
    release_detail = reopened.get(f"/api/releases/{demo.result.id}")
    outcomes = reopened.get("/api/outcomes")
    outcome_id = outcomes.json()["items"][0]["id"]
    outcome_detail = reopened.get(f"/api/outcomes/{outcome_id}")

    assert updated_trust.status_code == 200
    assert trust.json()["mode"] == "local_power_user"
    push_rule = next(rule for rule in trust.json()["rules"] if rule["key"] == "push_git_changes")
    assert push_rule["allowed"] is False
    assert push_rule["hard_blocked"] is True
    assert trust.json()["effective_policy_profile"] == "local_power_user"
    assert releases.status_code == 200
    assert releases.json()["items"][0]["id"] == demo.result.id
    assert release_detail.json()["advanced_optimization_details"]["pareto_frontier_ids"]
    assert release_detail.json()["advanced_optimization_details"]["qubo_problem_ids"]
    assert outcomes.status_code == 200
    assert outcome_detail.status_code == 200
    assert "LearningSignal" not in outcome_detail.text


def test_memory_crud_conflicts_and_suggestion_review(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    client = _client(database_path)
    session_id = client.post("/api/conversations", json={"title": "Memory review"}).json()["id"]

    first = client.post(
        "/api/memories",
        json={
            "kind": "strategic",
            "type": "strategic_decision",
            "content": "We should launch public alpha only after validation evidence is complete.",
            "summary": "Launch alpha after validation evidence",
            "scope": "project",
            "confidence": 0.82,
            "importance": 0.78,
            "stability": "long_term",
            "conversation_id": session_id,
            "evidence": [
                {
                    "content": "User explicitly asked for public-alpha readiness.",
                    "kind": "conversation",
                    "source_id": session_id,
                    "confidence": 0.9,
                }
            ],
        },
    )
    second = client.post(
        "/api/memories",
        json={
            "kind": "strategic",
            "type": "strategic_decision",
            "content": "Do not launch public alpha after validation evidence is complete.",
            "summary": "Do not launch alpha after validation evidence",
            "scope": "project",
        },
    )
    regular = client.post(
        "/api/memories",
        json={
            "kind": "regular",
            "type": "working_style",
            "content": "Prefer exact conversation exports over generated summaries.",
            "summary": "Export exact messages",
            "scope": "global",
            "source": "manual",
        },
    )
    listed = client.get("/api/memories?query=validation&type=strategic_decision&scope=project")
    conflict_detail = client.get(f"/api/memories/{first.json()['id']}")
    patched = client.patch(
        f"/api/memories/{first.json()['id']}",
        json={"summary": "Validate before alpha", "resolve_conflicts": True},
    )
    archived = client.post(f"/api/memories/{first.json()['id']}/archive")
    restored = client.post(f"/api/memories/{first.json()['id']}/restore")
    delete_without_confirm = client.request(
        "DELETE", f"/api/memories/{regular.json()['id']}", json={}
    )
    deleted = client.request(
        "DELETE", f"/api/memories/{regular.json()['id']}", json={"confirm": True}
    )

    ConversationRepository(database_path).save_memory_update(
        ConversationMemoryUpdate(
            session_id=session_id,
            candidate=ConversationMemoryCandidate(
                memory_type=MemoryType.PROJECT,
                content="Validation evidence should stay visible before releases.",
                summary="Keep release evidence visible",
                rationale="It changes release readiness decisions.",
                confidence=0.8,
                importance=0.7,
                stability="long_term",
            ),
        )
    )
    suggestions = client.get("/api/memory-suggestions")
    suggestion_id = suggestions.json()["suggestions"][0]["id"]
    saved_suggestion = client.post(f"/api/memory-suggestions/{suggestion_id}/save")
    ignored = client.post(f"/api/memory-suggestions/{suggestion_id}/ignore")

    assert first.status_code == 201
    assert second.status_code == 201
    assert "Potential conflict" in conflict_detail.json()["conflict_warnings"][0]
    assert listed.status_code == 200
    assert listed.json()["memories"]
    assert patched.json()["summary"] == "Validate before alpha"
    assert archived.json()["archived"] is True
    assert restored.json()["archived"] is False
    assert delete_without_confirm.status_code == 400
    assert deleted.status_code == 204
    assert suggestions.json()["total"] == 1
    assert saved_suggestion.status_code == 200
    assert saved_suggestion.json()["summary"] == "Keep release evidence visible"
    assert ignored.status_code == 204


def test_provider_settings_usage_export_and_backup_redaction(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    database_path = tmp_path / "hephaestus.db"
    client = _client(database_path)
    session_id = client.post("/api/conversations", json={"title": "Exact export"}).json()["id"]
    client.post(
        f"/api/conversations/{session_id}/messages",
        json={"content": "Please preserve exact chat history.", "provider": "local"},
    )

    provider = client.post(
        "/api/providers",
        json={
            "provider_type": "openai-compatible",
            "name": "Fake OpenAI Compatible",
            "model": "fake-chat",
            "base_url": "fake://openai-compatible",
            "api_key": "secret-token-123",
            "context_window": 32768,
            "input_cost_per_million": 0.1,
            "output_cost_per_million": 0.2,
            "default_for_conversation": True,
            "intended_roles": ["conversation", "coding"],
        },
    )
    provider_id = provider.json()["id"]
    tested = client.post(f"/api/providers/{provider_id}/test")
    updated = client.patch(
        f"/api/providers/{provider_id}",
        json={
            "provider_type": "openai-compatible",
            "name": "Fake OpenAI Compatible",
            "model": "fake-chat-v2",
            "base_url": "fake://openai-compatible",
            "api_key": None,
            "default_for_conversation": True,
        },
    )
    settings = client.patch(
        "/api/settings",
        json={"startup_route": "/memory", "appearance": "dark", "developer_details": True},
    )
    usage = client.get("/api/usage")
    markdown = client.post(f"/api/export/conversation/{session_id}", json={"format": "markdown"})
    exported_json = client.post(f"/api/export/conversation/{session_id}", json={"format": "json"})
    memory = client.post(
        "/api/memories",
        json={"kind": "strategic", "type": "preference", "content": "Never export API keys."},
    )
    memories_export = client.post("/api/export/memories")
    backup = client.post("/api/backup")
    restore = client.post(
        "/api/restore",
        json={"backup_path": backup.json()["path"], "confirm": True},
    )
    incompatible = tmp_path / "old-backup.db"
    with sqlite3.connect(incompatible) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (999, 'now')"
        )
    incompatible_restore = client.post(
        "/api/restore",
        json={"backup_path": str(incompatible), "confirm": True},
    )
    removed = client.delete(f"/api/providers/{provider_id}")

    assert provider.status_code == 201
    assert "secret-token-123" not in provider.text
    assert tested.json()["status"] == "configured"
    assert "secret-token-123" not in tested.text
    assert updated.json()["model"] == "fake-chat-v2"
    assert "secret-token-123" not in client.get("/api/providers").text
    assert settings.json()["settings"]["startup_route"] == "/memory"
    assert usage.json()["aggregate"]["deterministic_operations"] >= 1
    assert usage.json()["events"][0]["message"].startswith("Solved without a model call")
    assert markdown.json()["format"] == "markdown"
    assert "Please preserve exact chat history." in markdown.json()["content"]
    assert "summary" not in markdown.json()["content"].lower()
    assert exported_json.json()["format"] == "json"
    assert "secret-token-123" not in memories_export.text
    assert memory.status_code == 201
    assert backup.json()["schema_version"] == 21
    assert Path(backup.json()["path"]).exists()
    assert restore.json()["restored"] is True
    assert incompatible_restore.status_code == 400
    assert removed.status_code == 204


def test_advanced_decision_pareto_qubo_endpoints(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repo = _workbench_repo(tmp_path)
    client = _client(database_path)
    demo = ReleasePlanningOrchestrator(database_path).plan(
        ReleasePlanningRequest(path=str(repo), pareto=True, qubo=True, evaluate=True)
    )

    decisions = client.get("/api/advanced/decisions")
    trace_id = decisions.json()["decisions"][0]["id"]
    decision_detail = client.get(f"/api/advanced/decisions/{trace_id}")
    pareto_id = demo.result.pareto_frontier_ids[0]
    qubo_id = demo.result.qubo_problem_ids[0]
    pareto = client.get(f"/api/advanced/pareto/{pareto_id}")
    qubo = client.get(f"/api/advanced/qubo/{qubo_id}")

    assert decisions.status_code == 200
    assert decisions.json()["pareto_frontiers"]
    assert decisions.json()["qubo_problems"]
    assert decision_detail.status_code == 200
    assert "developer_payload" in decision_detail.json()
    assert pareto.status_code == 200
    assert "non-dominated" in pareto.json()["explanation"]
    assert pareto.json()["candidates"]
    assert qubo.status_code == 200
    assert "classical/local" in qubo.json()["explanation"]
    assert qubo.json()["variables"]


def test_packaged_static_asset_discovery(tmp_path) -> None:
    module_file = tmp_path / "site-packages" / "hephaestus" / "studio" / "security.py"
    static_dir = module_file.parent / "static"
    static_dir.mkdir(parents=True)
    module_file.write_text("# fixture\n", encoding="utf-8")
    (static_dir / "index.html").write_text("<main>Packaged Studio</main>", encoding="utf-8")

    assert resolve_static_dir(str(module_file)) == static_dir


def _workbench_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "workbench_repo"
    repo.mkdir(exist_ok=True)
    (repo / "README.md").write_text(
        "Hephaestus is a self-improving AI agent.\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                "name = 'workbench-fixture'",
                "version = '0.1.0'",
                "dependencies = ['pytest>=8.2']",
                "",
                "[tool.pytest.ini_options]",
                "testpaths = ['tests']",
            ]
        ),
        encoding="utf-8",
    )
    tests_dir = repo / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_sample.py").write_text(
        "def test_sample() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    return repo
