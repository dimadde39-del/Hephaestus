from hephaestus.optimize.context_packer import ContextCandidate, pack_context


def test_context_packer_includes_critical_item_when_possible() -> None:
    result = pack_context(
        [
            ContextCandidate(
                id="critical",
                relevance=0.6,
                importance=0.9,
                token_cost=500,
                critical=True,
            ),
            ContextCandidate(
                id="nice",
                relevance=0.9,
                importance=0.9,
                token_cost=800,
            ),
        ],
        token_budget=900,
    )

    assert [item.id for item in result.selected] == ["critical"]
    assert result.excluded[0].id == "nice"


def test_context_packer_reports_critical_item_that_cannot_fit() -> None:
    result = pack_context(
        [
            ContextCandidate(
                id="too-large",
                relevance=1.0,
                importance=1.0,
                token_cost=2_000,
                critical=True,
            )
        ],
        token_budget=500,
    )

    assert result.selected == []
    assert result.excluded[0].reason == "critical item did not fit token budget"
