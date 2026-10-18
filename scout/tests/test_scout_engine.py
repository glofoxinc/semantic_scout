"""Semantic Scout engine tests."""
from __future__ import annotations

from lib.git_scope import scope_violations
from lib.rdl_checks import country_column_first_ok
from lib.signoff_gate import run_signoff_checks


def test_country_column_mini_rdl():
    mini = """
    <Tablix Name="Tablix1"><TablixBody><TablixRows><TablixRow>
    <Value>Country</Value><Value>=Fields!country.Value</Value>
    </TablixRow></TablixRows></TablixBody></Tablix>
    """
    assert country_column_first_ok(mini)


def test_scope_warns_other_reports_on_ticket_mode():
    violations = scope_violations(
        [
            "New Members - Details.PaginatedReport/New Members - Details.rdl",
            "Other.PaginatedReport/Other.rdl",
        ],
        in_scope=["**/New Members - Details.rdl"],
        out_of_scope=[],
        scope_mode="ticket",
    )
    assert any(v["severity"] == "info" for v in violations)
    assert not any(v["severity"] == "blocker" for v in violations)


def test_signoff_checks_pass():
    result = run_signoff_checks()
    assert result["ok"] is True
