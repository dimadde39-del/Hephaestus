"""Deterministic policy request classifier."""

from __future__ import annotations

from collections.abc import Iterable

from hephaestus.policy.schemas import PolicyClassification, PolicyRiskCategory

_PRECEDENCE: tuple[PolicyRiskCategory, ...] = (
    PolicyRiskCategory.CREDENTIAL_OR_SECRET_EXPOSURE,
    PolicyRiskCategory.MALWARE_OR_ABUSE,
    PolicyRiskCategory.VIOLENCE_OR_PHYSICAL_HARM,
    PolicyRiskCategory.EXPLOITATION_OR_HARASSMENT,
    PolicyRiskCategory.DESTRUCTIVE_ACTION,
    PolicyRiskCategory.EXTERNAL_SIDE_EFFECT,
    PolicyRiskCategory.LOCAL_COMMAND_EXECUTION,
    PolicyRiskCategory.LOCAL_FILE_OPERATION,
    PolicyRiskCategory.REGULATED_HIGH_RISK,
    PolicyRiskCategory.SENSITIVE_PERSONAL_CONTEXT,
    PolicyRiskCategory.BENIGN_DEVELOPMENT,
    PolicyRiskCategory.BENIGN_CREATIVE,
    PolicyRiskCategory.BENIGN_RESEARCH,
    PolicyRiskCategory.STRATEGY_DISCUSSION,
)

_DEFENSIVE_CONTEXT = (
    "defensive",
    "defensively",
    "awareness",
    "training",
    "education",
    "educational",
    "explain",
    "how it works",
    "mitigation",
    "protect",
    "secure",
    "security tradeoff",
    "threat model",
    "architecture",
)


def classify_policy_request(text: str) -> PolicyClassification:
    """Classify a request into one or more stable policy categories."""

    normalized = _normalize(text)
    evidence: dict[PolicyRiskCategory, list[str]] = {}

    _add_if_matches(
        evidence,
        PolicyRiskCategory.CREDENTIAL_OR_SECRET_EXPOSURE,
        normalized,
        (
            "steal credentials",
            "steal passwords",
            "dump passwords",
            "dump credentials",
            "exfiltrate credentials",
            "exfiltrate secrets",
            "grab api keys",
            "steal api keys",
            "session cookies",
            "credential theft",
            "phish credentials",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.MALWARE_OR_ABUSE,
        normalized,
        (
            "deploy malware",
            "write malware",
            "build malware",
            "ransomware",
            "keylogger",
            "botnet",
            "persistence on victim",
            "bypass antivirus",
            "evade detection",
            "avoid detection",
            "abuse automation",
            "spam bot",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.VIOLENCE_OR_PHYSICAL_HARM,
        normalized,
        (
            "plan real-world violence",
            "kill someone",
            "hurt someone",
            "make a bomb",
            "build a bomb",
            "poison someone",
            "shoot up",
            "physical harm",
        ),
    )

    if not _has_defensive_context(normalized):
        _add_if_matches(
            evidence,
            PolicyRiskCategory.EXPLOITATION_OR_HARASSMENT,
            normalized,
            (
                "harass a specific person",
                "targeted harassment",
                "doxx",
                "dox ",
                "swat",
                "blackmail",
                "exploit a vulnerable",
                "hack into",
                "break into",
                "sql injection attack",
                "phishing kit",
                "scam",
            ),
        )

    _add_if_matches(
        evidence,
        PolicyRiskCategory.DESTRUCTIVE_ACTION,
        normalized,
        (
            "rm -rf",
            "remove-item",
            "delete generated files",
            "delete files",
            "wipe",
            "format drive",
            "drop database",
            "drop table",
            "destroy",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.EXTERNAL_SIDE_EFFECT,
        normalized,
        (
            "git push",
            "push to origin",
            "publish package",
            "npm publish",
            "deploy",
            "send a message",
            "send message externally",
            "email them",
            "post to twitter",
            "post to x",
            "open a pr",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.LOCAL_COMMAND_EXECUTION,
        normalized,
        (
            "run a shell command",
            "execute a shell command",
            "run rm",
            "run npm install",
            "run pnpm install",
            "run uv add",
            "run pip install",
            "install package dependencies",
            "install dependencies",
            "run command",
            "powershell",
            "bash command",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.LOCAL_FILE_OPERATION,
        normalized,
        (
            "edit files",
            "modify files",
            "move files",
            "rename files",
            "write to disk",
            "create files in my repo",
            "change files",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.REGULATED_HIGH_RISK,
        normalized,
        (
            "medical diagnosis",
            "legal advice",
            "tax advice",
            "financial advice",
            "investment advice",
            "prescribe",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.SENSITIVE_PERSONAL_CONTEXT,
        normalized,
        (
            "personal trauma",
            "self harm",
            "suicide",
            "my private life",
            "sensitive personal",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.BENIGN_CREATIVE,
        normalized,
        (
            "banner",
            "social preview",
            "readme",
            "mascot",
            "logo",
            "brand",
            "copy",
            "prompt",
            "non-corporate",
            "direct copy",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.BENIGN_DEVELOPMENT,
        normalized,
        (
            "write code",
            "local repo",
            "local project",
            "local development",
            "configure open-source",
            "configure open source",
            "debug",
            "github",
            "open-source tools",
            "open source tools",
            "sql injection works defensively",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.BENIGN_RESEARCH,
        normalized,
        (
            "research",
            "explain",
            "defensive",
            "defensively",
            "awareness training",
            "phishing awareness",
            "security tradeoffs",
            "security tradeoff",
            "architecture",
            "theory",
            "analysis",
        ),
    )
    _add_if_matches(
        evidence,
        PolicyRiskCategory.STRATEGY_DISCUSSION,
        normalized,
        (
            "brutally honest",
            "harshly",
            "harsh critique",
            "roadmap",
            "stress-test",
            "stress test",
            "startup idea",
            "business idea",
            "strategic risks",
            "strategy",
            "ambitious product",
        ),
    )

    categories = [category for category in _PRECEDENCE if category in evidence]
    if not categories:
        categories = [PolicyRiskCategory.BENIGN_RESEARCH]
        evidence[PolicyRiskCategory.BENIGN_RESEARCH] = ["default benign text request"]
    return PolicyClassification(categories=categories, evidence=evidence)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _has_defensive_context(text: str) -> bool:
    return any(marker in text for marker in _DEFENSIVE_CONTEXT)


def _add_if_matches(
    evidence: dict[PolicyRiskCategory, list[str]],
    category: PolicyRiskCategory,
    text: str,
    markers: Iterable[str],
) -> None:
    matches = [marker for marker in markers if marker in text]
    if matches:
        evidence.setdefault(category, []).extend(matches)
