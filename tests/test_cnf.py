import unittest

from sat import CNFFormula, solve_cnf, verify_cnf_assignment
from sat.verifier import verify_solver_result


class TestCNF(unittest.TestCase):

    def test_satisfiable_formula(self):
        """Проверяем формулу с существующим решением."""
        formula = CNFFormula()

        x = formula.new_variable("x")
        y = formula.new_variable("y")

        formula.add_clause([x, y])
        formula.add_clause([-x, y])

        result = solve_cnf(
            formula,
            backend="bruteforce",
        )

        self.assertEqual(result["status"], "SAT")

        verification = verify_solver_result(formula, result)

        self.assertEqual(
            verification["status"],
            "VERIFIED_SAT",
        )

    def test_unsatisfiable_formula(self):
        """Проверяем противоречивые ограничения."""
        formula = CNFFormula()

        x = formula.new_variable("x")

        formula.add_clause([x])
        formula.add_clause([-x])

        result = solve_cnf(
            formula,
            backend="bruteforce",
        )

        self.assertEqual(result["status"], "UNSAT")

    def test_invalid_assignment(self):
        """Верификатор должен отклонить неверное присваивание."""
        formula = CNFFormula()

        x = formula.new_variable("x")
        y = formula.new_variable("y")

        formula.add_clause([x, y])
        formula.add_clause([-x, y])

        result = verify_cnf_assignment(
            formula,
            {"x": True, "y": False},
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["failed_clauses"], [1])

    def test_dimacs_header_and_clauses(self):
        """Проверяем сериализацию CNF в DIMACS."""
        formula = CNFFormula()

        x = formula.new_variable("x")
        formula.add_clause([x])

        dimacs = formula.to_dimacs()

        self.assertIn("p cnf 1 1", dimacs)
        self.assertIn("1 0", dimacs)

    def test_xor_encoding(self):
        """Проверяем кодирование z = x XOR y."""
        formula = CNFFormula()

        x = formula.new_variable("x")
        y = formula.new_variable("y")
        z = formula.new_variable("z")

        formula.add_xor(x, y, z)

        # Проверяем все 8 возможных присваиваний.
        for xv in (False, True):
            for yv in (False, True):
                for zv in (False, True):
                    assignment = {
                        x: xv,
                        y: yv,
                        z: zv,
                    }

                    report = verify_cnf_assignment(
                        formula,
                        assignment,
                    )

                    self.assertEqual(
                        report["valid"],
                        zv == (xv != yv),
                        msg=(
                            f"Неверное XOR-кодирование для "
                            f"x={xv}, y={yv}, z={zv}"
                        ),
                    )

    def test_empty_clause_is_unsatisfiable(self):
        """Пустая дизъюнкция означает FALSE."""
        formula = CNFFormula()
        formula.new_variable("x")
        formula.add_clause([])

        result = solve_cnf(
            formula,
            backend="bruteforce",
        )

        self.assertEqual(result["status"], "UNSAT")


if __name__ == "__main__":
    unittest.main()