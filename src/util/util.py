from result import Result

from actions.action import Action, Context


async def preflight_execute(action: Action, ctx: Context) -> str:
    preflight = await action.preflight(ctx)
    if preflight.is_err():
        return action.preflight_wrap(preflight).unwrap_err()

    execute = await action.execute(ctx)
    return result_collapse(action.execute_wrap(execute))


def result_collapse[T](result: Result[T, T]) -> T:
    if result.is_ok():
        return result.unwrap()
    return result.unwrap_err()
