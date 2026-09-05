"""Section 10: Data validation.

Artifact generation is blocked on any validation error; warnings may
proceed. This module only checks arithmetic/internal consistency — it does
not re-derive football knowledge, just the invariants the spec lists.
"""
from __future__ import annotations

from .models import Dataset, ValidationResult

TOLERANCE = 0.5  # percentage-point / goal tolerance for rounded provider figures


def validate_dataset(dataset: Dataset, min_matches_for_confidence: int = 5) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    players = dataset.data.get("players", {})
    if not players:
        errors.append("Dataset has no player data.")
        return ValidationResult(status="failed", warnings=warnings, errors=errors)

    for name, stats in players.items():
        goals = stats.get("goals")
        shots = stats.get("shots")
        shots_on_target = stats.get("shots_on_target")
        minutes = stats.get("minutes")
        xg = stats.get("xg")
        conversion = stats.get("conversion")
        goals_minus_xg = stats.get("goals_minus_xg")
        apps = stats.get("apps")

        if goals is not None and shots is not None and goals > shots:
            errors.append(f"{name}: goals ({goals}) exceed shots ({shots}).")

        if shots_on_target is not None and shots is not None and shots_on_target > shots:
            errors.append(
                f"{name}: shots on target ({shots_on_target}) exceed shots ({shots})."
            )

        if minutes is not None and minutes < 0:
            errors.append(f"{name}: minutes played is negative ({minutes}).")

        if xg is not None and xg < 0:
            errors.append(f"{name}: xG is negative ({xg}).")

        if conversion is not None and goals is not None and shots:
            expected = 100 * goals / shots
            if abs(conversion - expected) > TOLERANCE:
                errors.append(
                    f"{name}: conversion ({conversion}) does not match goals/shots "
                    f"({expected:.2f})."
                )

        if goals_minus_xg is not None and goals is not None and xg is not None:
            expected = goals - xg
            if abs(goals_minus_xg - expected) > TOLERANCE:
                errors.append(
                    f"{name}: goals_minus_xg ({goals_minus_xg}) does not match "
                    f"goals - xG ({expected:.2f})."
                )

        if apps is not None and apps < min_matches_for_confidence:
            warnings.append(
                f"{name}: only {apps} league matches have been played — "
                f"treat rates as provisional."
            )

    # A single Dataset already carries one provider/competition/season/capture
    # window by construction (see data_agent.py's one-provider-per-story rule),
    # so no separate cross-player metadata check is needed here.
    status = "failed" if errors else "passed"
    return ValidationResult(status=status, warnings=warnings, errors=errors)
