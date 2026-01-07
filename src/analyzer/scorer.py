"""
Test priority scoring for determining which business logic is most important to test.

Uses heuristics to score extracted business logic based on:
- Criticality (does it affect money, data, security?)
- Complexity (is it error-prone?)
- Coverage (is it a public API?)
- Historical signals (from git if available)
"""

from dataclasses import dataclass
from typing import List
from .extractor import BusinessPolicy, TestableScenario, ExtractedLogic


@dataclass
class ScoredScenario:
    """A testable scenario with a priority score."""
    scenario: TestableScenario
    score: float
    reasons: List[str]  # Why it got this score


class TestPriorityScorer:
    """Score and prioritize testable scenarios."""

    def __init__(self):
        # Keywords that indicate high priority
        self.critical_keywords = {
            'payment', 'refund', 'charge', 'money', 'price', 'cost',
            'auth', 'login', 'password', 'security', 'permission',
            'delete', 'remove', 'cancel', 'terminate',
            'email', 'notification', 'alert',
        }

        self.complexity_keywords = {
            'retry', 'fallback', 'timeout', 'async', 'concurrent',
            'transaction', 'rollback', 'compensate',
        }

    def score_scenarios(self, logic: ExtractedLogic) -> List[ScoredScenario]:
        """
        Score all scenarios and return them prioritized.

        Args:
            logic: Extracted business logic

        Returns:
            List of scenarios sorted by priority (highest first)
        """
        scored = []

        for scenario in logic.scenarios:
            score, reasons = self._calculate_score(scenario, logic)
            scored.append(ScoredScenario(
                scenario=scenario,
                score=score,
                reasons=reasons
            ))

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored

    def _calculate_score(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> tuple[float, List[str]]:
        """Calculate priority score for a scenario."""
        score = 0.0
        reasons = []

        # Base score by type
        if scenario.scenario_type == 'error_path':
            score += 2.0
            reasons.append("Error path (important to handle failures)")
        elif scenario.scenario_type == 'edge_case':
            score += 1.5
            reasons.append("Edge case (catches unexpected inputs)")
        elif scenario.scenario_type == 'happy_path':
            score += 1.0
            reasons.append("Happy path (core functionality)")

        # Critical domain scoring
        scenario_text = f"{scenario.name} {scenario.description}".lower()

        for keyword in self.critical_keywords:
            if keyword in scenario_text:
                score += 2.5
                reasons.append(f"Critical domain: {keyword}")
                break  # Only count once

        # Complexity scoring
        for keyword in self.complexity_keywords:
            if keyword in scenario_text:
                score += 1.5
                reasons.append(f"Complex logic: {keyword}")
                break

        # Policy-related scoring
        if scenario.related_policies:
            score += len(scenario.related_policies) * 0.5
            reasons.append(f"Related to {len(scenario.related_policies)} policies")

        # Name-based heuristics
        if 'refund' in scenario.name.lower():
            score += 3.0
            reasons.append("Refund logic (high business impact)")

        if 'auth' in scenario.name.lower() or 'login' in scenario.name.lower():
            score += 3.0
            reasons.append("Authentication logic (security critical)")

        if 'payment' in scenario.name.lower() or 'charge' in scenario.name.lower():
            score += 3.0
            reasons.append("Payment logic (money involved)")

        if 'delete' in scenario.name.lower() or 'remove' in scenario.name.lower():
            score += 2.0
            reasons.append("Destructive action (data loss risk)")

        return score, reasons

    def filter_by_threshold(
        self,
        scored: List[ScoredScenario],
        threshold: float = 5.0
    ) -> List[ScoredScenario]:
        """
        Filter scenarios to only those above a score threshold.

        Args:
            scored: List of scored scenarios
            threshold: Minimum score to include

        Returns:
            Filtered list
        """
        return [s for s in scored if s.score >= threshold]

    def top_n(self, scored: List[ScoredScenario], n: int) -> List[ScoredScenario]:
        """
        Get the top N highest priority scenarios.

        Args:
            scored: List of scored scenarios
            n: Number to return

        Returns:
            Top N scenarios
        """
        return scored[:n]


if __name__ == '__main__':
    # Example usage
    from .parser import CodeParser
    from .extractor import BusinessLogicExtractor
    from pathlib import Path

    # Parse and extract
    parser = CodeParser()
    extractor = BusinessLogicExtractor()
    scorer = TestPriorityScorer()

    analyses = parser.parse_directory(Path('./example_codebase'))
    logic = extractor.extract(analyses)

    # Score scenarios
    scored = scorer.score_scenarios(logic)

    print(f"\nTop 10 priority test scenarios:")
    print("=" * 80)

    for i, item in enumerate(scored[:10], 1):
        print(f"\n{i}. {item.scenario.name} (Score: {item.score:.1f})")
        print(f"   Type: {item.scenario.scenario_type}")
        print(f"   Reasons:")
        for reason in item.reasons:
            print(f"     - {reason}")
