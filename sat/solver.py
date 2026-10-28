"""SAT solver adapter with optional backends and a small brute-force solver."""

from __future__ import annotations

from itertools import product
from time import perf_counter

from .cnf_builder import CNFFormula


def _verify_literals(
    formula: CNFFormula,
    assignment: dict[int, bool],
) -> bool:
    """Check every clause using an assignment keyed by variable ID."""
    for clause in formula.clauses:
        if not any(
            assignment[abs(literal)] == (literal > 0)
            for literal in clause
        ):
            return False
    return True


def _normalize_model(
    formula: CNFFormula,
    model: list[int],
) -> dict[int, bool]:
    """Convert signed literals into a complete assignment."""
    assignment = {var_id: False for var_id in range(1, formula.num_vars + 1)}

    for literal in model:
        if literal == 0:
            continue
        var_id = abs(literal)
        if var_id > formula.num_vars:
            raise ValueError(f"Solver returned invalid literal: {literal}")
        assignment[var_id] = literal > 0

    return assignment


def _format_result(
    formula: CNFFormula,
    status: str,
    backend: str,
    started: float,
    assignment: dict[int, bool] | None = None,
    reason: str | None = None,
) -> dict:
    """Build the common result structure used by every backend."""
    named_assignment = None

    if assignment is not None:
        named_assignment = {
            name: assignment[var_id]
            for name, var_id in formula.variable_names.items()
        }

    return {
        "status": status,
        "backend": backend,
        "elapsed_seconds": round(perf_counter() - started, 6),
        "assignment": named_assignment,
        "assignment_by_id": (
            {str(k): v for k, v in assignment.items()}
            if assignment is not None
            else None
        ),
        "reason": reason,
    }


def _solve_with_pysat(
    formula: CNFFormula,
    solver_name: str = "g3",
) -> tuple[str, dict[int, bool] | None]:
    """Solve with python-sat, if installed."""
    from pysat.solvers import Solver

    with Solver(
        name=solver_name,
        bootstrap_with=formula.clauses,
    ) as solver:
        satisfiable = solver.solve()

        if not satisfiable:
            return "UNSAT", None

        model = solver.get_model() or []
        assignment = _normalize_model(formula, model)

        if not _verify_literals(formula, assignment):
            return "UNKNOWN", None

        return "SAT", assignment


def _solve_with_pycosat(
    formula: CNFFormula,
) -> tuple[str, dict[int, bool] | None]:
    """Solve with pycosat, if installed."""
    import pycosat

    result = pycosat.solve(
        formula.clauses,
        vars=formula.num_vars,
    )

    if result == "UNSAT":
        return "UNSAT", None

    if result == "UNKNOWN":
        return "UNKNOWN", None

    assignment = _normalize_model(formula, result)

    if not _verify_literals(formula, assignment):
        return "UNKNOWN", None

    return "SAT", assignment


def _solve_bruteforce(
    formula: CNFFormula,
    max_variables: int,
) -> tuple[str, dict[int, bool] | None]:
    """Exhaustively search all assignments for small formulas."""
    if formula.num_vars > max_variables:
        return "UNKNOWN", None

    for values in product((False, True), repeat=formula.num_vars):
        assignment = {
            var_id: values[var_id - 1]
            for var_id in range(1, formula.num_vars + 1)
        }

        if _verify_literals(formula, assignment):
            return "SAT", assignment

    return "UNSAT", None


def solve_cnf(
    formula: CNFFormula,
    backend: str = "auto",
    max_bruteforce_vars: int = 24,
    pysat_solver: str = "g3",
) -> dict:
    """
    Solve a CNF formula.

    backend:
        "auto"       Try python-sat, then pycosat, then brute force.
        "pysat"      Require python-sat.
        "pycosat"    Require pycosat.
        "bruteforce" Use exhaustive search only.

    A SAT result is checked against the formula before it is returned.
    """
    if backend not in {"auto", "pysat", "pycosat", "bruteforce"}:
        raise ValueError(f"Unsupported backend: {backend}")

    if max_bruteforce_vars < 0:
        raise ValueError("max_bruteforce_vars must be non-negative")

    started = perf_counter()
    attempts: list[str] = []

    if backend in {"auto", "pysat"}:
        try:
            status, assignment = _solve_with_pysat(
                formula,
                solver_name=pysat_solver,
            )
            return _format_result(
                formula, status, "pysat", started, assignment
            )
        except ImportError:
            attempts.append("python-sat is not installed")
            if backend == "pysat":
                raise RuntimeError(
                    "Backend 'pysat' requires the optional package "
                    "'python-sat'. Install it with: "
                    "python -m pip install python-sat"
                )
        except Exception as exc:
            if backend == "pysat":
                raise RuntimeError(f"PySAT failed: {exc}") from exc
            attempts.append(f"python-sat failed: {exc}")

    if backend in {"auto", "pycosat"}:
        try:
            status, assignment = _solve_with_pycosat(formula)
            return _format_result(
                formula, status, "pycosat", started, assignment
            )
        except ImportError:
            attempts.append("pycosat is not installed")
            if backend == "pycosat":
                raise RuntimeError(
                    "Backend 'pycosat' requires the optional package "
                    "'pycosat'. Install it with: "
                    "python -m pip install pycosat"
                )
        except Exception as exc:
            if backend == "pycosat":
                raise RuntimeError(f"pycosat failed: {exc}") from exc
            attempts.append(f"pycosat failed: {exc}")

    status, assignment = _solve_bruteforce(
        formula,
        max_variables=max_bruteforce_vars,
    )

    reason = None
    if status == "UNKNOWN":
        reason = (
            f"Brute-force limit exceeded: {formula.num_vars} variables, "
            f"limit {max_bruteforce_vars}. "
            + "; ".join(attempts)
        )

    return _format_result(
        formula,
        status,
        "bruteforce",
        started,
        assignment,
        reason=reason,
    )