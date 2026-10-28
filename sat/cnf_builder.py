"""Build and serialize Boolean formulas in conjunctive normal form (CNF)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class CNFFormula:
    """
    CNF formula represented as a list of clauses.

    A literal is a non-zero integer:
        1  means variable 1
       -1  means NOT variable 1

    A clause is a disjunction of literals.
    The formula is a conjunction of clauses.
    """

    num_vars: int = 0
    clauses: list[list[int]] = field(default_factory=list)
    variable_names: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.num_vars < 0:
            raise ValueError("num_vars must be non-negative")

        for name, var_id in self.variable_names.items():
            if not isinstance(name, str) or not name:
                raise ValueError("Variable names must be non-empty strings")
            if not isinstance(var_id, int) or isinstance(var_id, bool):
                raise ValueError(f"Invalid variable ID for {name!r}")
            if not 1 <= var_id <= self.num_vars:
                raise ValueError(
                    f"Variable ID {var_id} is outside 1..{self.num_vars}"
                )

        for clause in self.clauses:
            self._validate_clause(clause)

    @property
    def variable_ids(self) -> dict[str, int]:
        """Return a copy of the name-to-ID mapping."""
        return dict(self.variable_names)

    @property
    def id_to_name(self) -> dict[int, str]:
        """Return the inverse variable mapping."""
        return {
            var_id: name
            for name, var_id in self.variable_names.items()
        }

    def new_variable(self, name: str | None = None) -> int:
        """Create a Boolean variable and return its positive integer ID."""
        if name is not None:
            if not isinstance(name, str) or not name:
                raise ValueError("Variable name must be a non-empty string")
            if name in self.variable_names:
                raise ValueError(f"Variable already exists: {name}")

        self.num_vars += 1
        var_id = self.num_vars

        if name is not None:
            self.variable_names[name] = var_id

        return var_id

    def get_variable(self, name: str) -> int:
        """Get the ID of an existing named variable."""
        try:
            return self.variable_names[name]
        except KeyError as exc:
            raise KeyError(f"Unknown variable: {name}") from exc

    def literal(self, name: str, negated: bool = False) -> int:
        """Return a signed literal for an existing named variable."""
        var_id = self.get_variable(name)
        return -var_id if negated else var_id

    def add_clause(self, literals: Iterable[int]) -> None:
        """
        Add a clause.

        An empty clause represents FALSE, making the formula unsatisfiable.
        Duplicate literals are removed. A clause containing both x and -x
        is always true and is therefore stored as a tautology.
        """
        clause = list(literals)
        self._validate_clause(clause)

        # Remove duplicate literals while preserving order.
        normalized: list[int] = []
        seen: set[int] = set()

        for literal in clause:
            if literal not in seen:
                normalized.append(literal)
                seen.add(literal)

        self.clauses.append(normalized)

    def _validate_clause(self, clause: Iterable[int]) -> None:
        for literal in clause:
            if not isinstance(literal, int) or isinstance(literal, bool):
                raise TypeError(
                    f"Literal must be an integer, got {literal!r}"
                )
            if literal == 0:
                raise ValueError("Literal 0 is not allowed")
            if abs(literal) > self.num_vars:
                raise ValueError(
                    f"Literal {literal} references a variable "
                    f"outside 1..{self.num_vars}"
                )

    def add_unit(self, literal: int) -> None:
        """Add a unit clause containing one literal."""
        self.add_clause([literal])

    def add_implication(self, a: int, b: int) -> None:
        """Encode a => b as (NOT a OR b)."""
        self.add_clause([-a, b])

    def add_equivalence(self, a: int, b: int) -> None:
        """Encode a <=> b."""
        self.add_clause([-a, b])
        self.add_clause([a, -b])

    def add_and(self, a: int, b: int, out: int) -> None:
        """Encode out <=> (a AND b)."""
        self.add_clause([-out, a])
        self.add_clause([-out, b])
        self.add_clause([out, -a, -b])

    def add_or(self, a: int, b: int, out: int) -> None:
        """Encode out <=> (a OR b)."""
        self.add_clause([out, -a])
        self.add_clause([out, -b])
        self.add_clause([-out, a, b])

    def add_xor(self, a: int, b: int, out: int) -> None:
        """Encode out <=> (a XOR b)."""
        self.add_clause([-a, -b, -out])
        self.add_clause([a, b, -out])
        self.add_clause([a, -b, out])
        self.add_clause([-a, b, out])

    def to_dimacs(self) -> str:
        """Serialize the formula in DIMACS CNF format."""
        lines = [
            f"p cnf {self.num_vars} {len(self.clauses)}"
        ]

        for clause in self.clauses:
            lines.append(" ".join(map(str, clause)) + " 0")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation."""
        return {
            "num_vars": self.num_vars,
            "num_clauses": len(self.clauses),
            "variable_names": dict(self.variable_names),
            "clauses": [list(clause) for clause in self.clauses],
        }

    def save_dimacs(self, path: str) -> None:
        """Write the formula to a DIMACS CNF file."""
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            file.write(self.to_dimacs())