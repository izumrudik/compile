from dataclasses import dataclass
from enum import Enum, auto
import sys
from typing import ClassVar, NoReturn
from .token import Loc
__all__ = (
	"ET",
	"Error",
	"add_error",
	"show_errors",
	"create_critical_error",
)

class ET(Enum):# Error Type
	ILLEGAL_CHAR = auto()
	def __str__(self) -> str:
		return f"{self.name.lower().replace('_','-')}"

@dataclass(slots=True, frozen=True)
class Error:
	loc:Loc
	typ:ET
	msg:str
	errors:'ClassVar[list[Error]]' = []
def add_error(err:ET,loc:'Loc',msg:'str') -> None:
	Error.errors.append(Error(loc,err,msg))

def show_errors() -> None|NoReturn:
	if len(Error.errors) == 0:
		return None
	crash_with_errors()

def crash_with_errors() -> NoReturn:
	assert len(Error.errors) != 0, "crash_with_errors should be called only with errors"

	for error in Error.errors:
		print(f"ERROR: {error.loc} {error.msg} [{error.typ}]", file=sys.stderr, flush=True)

	if len(Error.errors) >= 256:
		sys.exit(1)
	else:
		sys.exit(len(Error.errors))

def create_critical_error(err:ET,loc:'Loc', msg:'str') -> NoReturn:
	Error.errors.append(Error(loc,err,msg))
	crash_with_errors()