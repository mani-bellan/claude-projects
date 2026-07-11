Generate comprehensive pytest tests for the code in $ARGUMENTS or the current selection.

Rules:
- Use `pytest` with `pytest.mark.parametrize` for data-driven cases
- Cover: happy path, edge cases (empty, None, boundary values), and expected failure paths
- Mock external dependencies (network, filesystem, databases) with `unittest.mock`
- Each test function must have a docstring explaining what it verifies
- Group tests in a class named `Test<FunctionOrClassName>`
- Add a module-level docstring explaining the overall test strategy

Write the tests to a file named `tests/test_<source_module>.py` and confirm the path when done.
