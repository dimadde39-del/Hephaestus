from hephaestus.safety.policy import SafetyPolicy
from hephaestus.tools.filesystem import filesystem_tools


def test_safety_policy_blocks_dangerous_shell_command() -> None:
    decision = SafetyPolicy().evaluate_shell_command("rm -rf .")

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "recursive force delete" in decision.reasons


def test_safety_policy_allows_read_only_tool() -> None:
    read_tool = filesystem_tools()[0]

    decision = SafetyPolicy().evaluate_tool(read_tool)

    assert decision.allowed is True
    assert decision.requires_approval is False


def test_safety_policy_gates_write_tool() -> None:
    write_tool = filesystem_tools()[1]

    decision = SafetyPolicy().evaluate_tool(write_tool)

    assert decision.allowed is False
    assert decision.requires_approval is True
