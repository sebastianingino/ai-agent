from dataclasses import dataclass, field
from typing import Collection, Dict, List, Optional, Union


class ArgParser:
    @dataclass
    class Arg:
        name: str
        short_name: Optional[str]
        default: Optional[str]
        _value: List[str] = field(default_factory=list)

        def reset(self):
            self._value = []

        def append(self, value: str):
            self._value.append(value)

        def value(self) -> Optional[str]:
            return " ".join(self._value) if self._value else self.default

    args: Dict[str, Arg]
    short_args: Dict[str, Arg]

    def __init__(self, args: Optional[List[Arg]] = None):
        self.args = {arg.name: arg for arg in args} if args else {}
        self.short_args = (
            {arg.short_name: arg for arg in args if arg.short_name} if args else {}
        )

    def add_argument(
        self,
        name: str,
        short_name: Optional[str] = None,
        default: Optional[str] = None,
    ):
        self.args[name] = self.Arg(name, short_name, default)
        if short_name:
            self.short_args[short_name] = self.args[name]

    def __getattr__(self, name: str) -> Optional[str]:
        if name in self.args:
            return self.args[name].value()
        elif name in self.short_args:
            return self.short_args[name].value()
        else:
            raise AttributeError(f"Arg {name} not found.")

    def parse(self, input: Union[str, Collection[str]]) -> str:
        for arg in self.args.values():
            arg.reset()

        result: List[str] = []
        cur_arg = None
        if isinstance(input, str):
            input = input.split()
        for val in input:
            if val.startswith("--"):
                cur_arg = self.args.get(val[2:])
            elif val.startswith("-"):
                cur_arg = self.short_args.get(val[1:])
            else:
                (cur_arg or result).append(val)
        return " ".join(result)
