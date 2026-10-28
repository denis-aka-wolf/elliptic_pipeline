from sat import CNFFormula, solve_cnf, verify_cnf_assignment
from sat.verifier import verify_solver_result


def main():
    formula = CNFFormula()

    # Создаём переменные x и y.
    x = formula.new_variable("x")
    y = formula.new_variable("y")

    # Формула:
    # (x OR y) AND (NOT x OR y)
    formula.add_clause([x, y])
    formula.add_clause([-x, y])

    print("=== DIMACS CNF ===")
    print(formula.to_dimacs())

    result = solve_cnf(formula, backend="auto")

    print("=== SOLVER RESULT ===")
    print(result)

    verification = verify_solver_result(formula, result)

    print("=== VERIFICATION ===")
    print(verification)

    assert result["status"] == "SAT"
    assert verification["status"] == "VERIFIED_SAT"

    # Проверяем заведомо неверное решение.
    bad_assignment = {"x": True, "y": False}
    bad_result = verify_cnf_assignment(formula, bad_assignment)

    print("=== INVALID ASSIGNMENT TEST ===")
    print(bad_result)

    assert bad_result["valid"] is False

    # Теперь добавим противоречивые ограничения: x и NOT x.
    impossible = CNFFormula()
    z = impossible.new_variable("z")
    impossible.add_clause([z])
    impossible.add_clause([-z])

    impossible_result = solve_cnf(
        impossible,
        backend="bruteforce",
    )

    print("=== UNSAT TEST ===")
    print(impossible_result)

    assert impossible_result["status"] == "UNSAT"

    print("ALL SAT TESTS PASSED")


if __name__ == "__main__":
    main()