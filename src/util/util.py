from result import Result


def result_collapse[T](result: Result[T, T]) -> T:
    if result.is_ok():
        return result.unwrap()
    return result.unwrap_err()
