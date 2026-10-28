"""Independent verification of SAT assignments and CNF formulas."""

from __future__ import annotations

from .cnf_builder import CNFFormula


def verify_cnf_assignment(
    formula: CNFFormula,
    assignment: dict,
) -> dict:
    """
    Verify an assignment against every clause.

    Assignment keys may be variable IDs or names.
    Values must be Boolean or integer 0/1.

    Returns a report with an overall result and failed clause indices.
    Clause indices in the report start at zero.
    """
    if not isinstance(assignment, dict):
        raise TypeError("assignment must be a dictionary")

    normalized: dict[int, bool] = {}

    for var_id in range(1, formula.num_vars + 1):
        if var_id in assignment:
            raw_value = assignment[var_id]
        elif str(var_id) in assignment:
            raw_value = assignment[str(var_id)]
        else:
            name = formula.id_to_name.get(var_id)
            if name is not None and name in assignment:
                raw_value = assignment[name]
            else:
                return {
                    "valid": False,
                    "complete": False,
                    "checked_clauses": 0,
                    "failed_clauses": [],
                    "error": f"Missing assignment for variable {var_id}",
                }

        if raw_value not in (0, 1, False, True):
            return {
                "valid": False,
                "complete": False,
                "checked_clauses": 0,
                "failed_clauses": [],
                "error": (
                    f"Variable {var_id} must have a Boolean value, "
                    f"got {raw_value!r}"
                ),
            }

        normalized[var_id] = bool(raw_value)

    failed_clauses: list[int] = []

    for clause_index, clause in enumerate(formula.clauses):
        satisfied = any(
            normalized[abs(literal)] == (literal > 0)
            for literal in clause
        )

        if not satisfied:
            failed_clauses.append(clause_index)

    return {
        "valid": not failed_clauses,
        "complete": True,
        "checked_clauses": len(formula.clauses),
        "failed_clauses": failed_clauses,
        "error": None,
    }


def verify_solver_result(
    formula: CNFFormula,
    solver_result: dict,
) -> dict:
    """
    Independently verify a result returned by solve_cnf().

    SAT results are accepted only if their assignment satisfies the formula.
    UNSAT is reported as a solver claim, not an independently proven result.
    """
    status = solver_result.get("status")

    if status == "SAT":
        assignment = solver_result.get("assignment_by_id")

        if assignment is None:
            return {
                "valid": False,
                "status": "INVALID_RESULT",
                "error": "SAT result has no assignment",
            }

        report = verify_cnf_assignment(formula, assignment)

        return {
            **report,
            "status": "VERIFIED_SAT" if report["valid"] else "INVALID_SAT",
        }

    if status == "UNSAT":
        return {
            "valid": None,
            "status": "UNSAT_CLAIM",
            "error": (
                "The solver reports UNSAT. This verifier checks candidate "
                "assignments, but does not independently prove unsatisfiability."
            ),
        }

    return {
        "valid": None,
        "status": "UNKNOWN",
        "error": solver_result.get("reason") or "No definitive solver result",
    }