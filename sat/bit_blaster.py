from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BitVector:
    """Массив булевых переменных, от младшего бита к старшему."""
    bits: tuple[int, ...]

    def __len__(self) -> int:
        return len(self.bits)


class CNFBuilder:
    """Построитель CNF в формате DIMACS."""

    def __init__(self) -> None:
        self.next_var = 1
        self.clauses: list[tuple[int, ...]] = []
        self.names: dict[str, int] = {}

    def new_var(self, name: str | None = None) -> int:
        var = self.next_var
        self.next_var += 1

        if name is not None:
            if name in self.names:
                raise ValueError(f"Повторное имя переменной: {name}")
            self.names[name] = var

        return var

    def add_clause(self, *literals: int) -> None:
        if any(lit == 0 for lit in literals):
            raise ValueError("Литерал 0 зарезервирован для DIMACS.")

        self.clauses.append(tuple(literals))

    def force(self, var: int, value: bool) -> None:
        self.add_clause(var if value else -var)

    def equivalent(self, a: int, b: int) -> None:
        self.add_clause(-a, b)
        self.add_clause(a, -b)

    def gate_not(self, out: int, a: int) -> None:
        self.add_clause(-out, -a)
        self.add_clause(out, a)

    def gate_and(self, out: int, a: int, b: int) -> None:
        self.add_clause(-out, a)
        self.add_clause(-out, b)
        self.add_clause(out, -a, -b)

    def gate_or(self, out: int, a: int, b: int) -> None:
        self.add_clause(out, -a)
        self.add_clause(out, -b)
        self.add_clause(-out, a, b)

    def gate_xor(self, out: int, a: int, b: int) -> None:
        self.add_clause(-out, -a, -b)
        self.add_clause(-out, a, b)
        self.add_clause(out, -a, b)
        self.add_clause(out, a, -b)

    def gate_majority(
        self,
        out: int,
        a: int,
        b: int,
        c: int,
    ) -> None:
        """out = majority(a, b, c)."""
        self.add_clause(-a, -b, out)
        self.add_clause(-a, -c, out)
        self.add_clause(-b, -c, out)

        self.add_clause(a, b, -out)
        self.add_clause(a, c, -out)
        self.add_clause(b, c, -out)

    def full_adder(
        self,
        a: int,
        b: int,
        carry_in: int,
    ) -> tuple[int, int]:
        """Возвращает (sum_bit, carry_out)."""
        ab = self.new_var()
        self.gate_xor(ab, a, b)

        sum_bit = self.new_var()
        self.gate_xor(sum_bit, ab, carry_in)

        carry_out = self.new_var()
        self.gate_majority(carry_out, a, b, carry_in)

        return sum_bit, carry_out

    def constant_bits(self, value: int, width: int) -> BitVector:
        if value < 0:
            raise ValueError("Ожидается неотрицательная константа.")
        if width <= 0:
            raise ValueError("Ширина должна быть положительной.")
        if value >= (1 << width):
            raise ValueError("Константа не помещается в заданную ширину.")

        bits = []

        for i in range(width):
            bit = self.new_var()
            self.force(bit, bool((value >> i) & 1))
            bits.append(bit)

        return BitVector(tuple(bits))

    def new_vector(self, width: int, prefix: str) -> BitVector:
        if width <= 0:
            raise ValueError("Ширина должна быть положительной.")

        return BitVector(
            tuple(
                self.new_var(f"{prefix}_{i}")
                for i in range(width)
            )
        )

    def add_vectors(
        self,
        a: BitVector,
        b: BitVector,
        width: int | None = None,
    ) -> BitVector:
        """Сложение с фиксированной шириной результата.

        Переполнение за пределами ширины отбрасывается.
        """
        if width is None:
            width = max(len(a), len(b))

        if width <= 0:
            raise ValueError("Ширина результата должна быть положительной.")

        zero = self.new_var()
        self.force(zero, False)

        carry = zero
        result = []

        for i in range(width):
            ai = a.bits[i] if i < len(a) else zero
            bi = b.bits[i] if i < len(b) else zero

            s, carry = self.full_adder(ai, bi, carry)
            result.append(s)

        return BitVector(tuple(result))

    def mul_by_const(
        self,
        vector: BitVector,
        constant: int,
        width: int,
    ) -> BitVector:
        """Умножение на неотрицательную константу.

        Результат вычисляется в фиксированной ширине.
        При необходимости вызывающая сторона должна
        обеспечить достаточную ширину, чтобы не потерять
        значимые старшие биты.
        """
        if constant < 0:
            raise ValueError("Константа должна быть неотрицательной.")

        if width <= 0:
            raise ValueError("Ширина результата должна быть положительной.")

        zero = self.new_var()
        self.force(zero, False)

        total = BitVector(tuple(zero for _ in range(width)))

        for shift in range(constant.bit_length()):
            if not ((constant >> shift) & 1):
                continue

            partial_bits = []

            for i in range(width):
                source_index = i - shift

                if source_index < 0 or source_index >= len(vector):
                    partial_bits.append(zero)
                else:
                    partial_bits.append(vector.bits[source_index])

            partial = BitVector(tuple(partial_bits))
            total = self.add_vectors(total, partial, width)

        return total

    def equal_vectors(
        self,
        a: BitVector,
        b: BitVector,
    ) -> None:
        width = max(len(a), len(b))

        zero = self.new_var()
        self.force(zero, False)

        for i in range(width):
            ai = a.bits[i] if i < len(a) else zero
            bi = b.bits[i] if i < len(b) else zero
            self.equivalent(ai, bi)

    def write_dimacs(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="ascii", newline="\n") as file:
            file.write(
                f"p cnf {self.next_var - 1} {len(self.clauses)}\n"
            )

            for clause in self.clauses:
                file.write(
                    " ".join(map(str, clause)) + " 0\n"
                )

    def variable_count(self) -> int:
        return self.next_var - 1

    def clause_count(self) -> int:
        return len(self.clauses)