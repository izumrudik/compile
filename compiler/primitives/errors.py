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
	"exit_properly",
)

class ET(Enum):# Error Type
	ANY_CHAR = auto()
	CHARACTER = auto()
	DIVISION = auto()
	ILLEGAL_CHAR = auto()
	NO_USE_NAME = auto()
	NO_USE_PAREN = auto()
	NO_USE_COMMA = auto()
	NO_CONST_NAME = auto()
	NO_FROM_IMPORT = auto()
	NO_FROM_NAME = auto()
	NO_FROM_2NAME = auto()
	NO_STRUCT_NAME = auto()
	NO_MIX_NAME = auto()
	UNRECOGNIZED_TOP = auto()
	NO_MIX_MIXED_NAME = auto()
	NO_PACKET_NAME = auto()
	NO_PACKET = auto()
	NO_DIR = auto()
	NO_MODULE_NAME = auto()
	NO_MODULE = auto()
	RECURSION = auto()
	NO_GENERIC_PERCENT = auto()
	NO_GENERIC_NAME = auto()
	NO_FUN_NAME = auto()
	NO_FUN_PAREN = auto()
	NO_FUN_COMMA = auto()
	UNRECOGNIZED_STRUCT_STATEMENT = auto()
	UNRECOGNIZED_CTE_TERM = auto()
	CTE_ZERO_DIV = auto()
	CTE_ZERO_MOD = auto()
	NO_DECLARATION_BRACKET = auto()
	NO_SET_NAME = auto()
	NO_SET_EQUALS = auto()
	NO_TYPED_VAR_NAME = auto()
	NO_COLON = auto()
	NO_ARRAY_BRACKET = auto()
	NO_SUBSCRIPT_BRACKET = auto()
	NO_NEWLINE = auto()
	NO_CALL_COMMA = auto()
	NO_BLOCK_START = auto()
	NO_WORD_REF = auto()
	UNRECOGNIZED_TYPE = auto()
	NO_GENERIC_COMMA = auto()
	NO_EXPR_PAREN = auto()
	NO_CAST_RPAREN = auto()
	NO_CAST_COMMA = auto()
	NO_GENERIC_TYPE_NAME = auto()
	NO_FIELD_NAME = auto()
	NO_CAST_LPAREN = auto()
	NO_FUN_TYP_COMMA = auto()
	NO_TERM = auto()
	def __str__(self) -> str:
		return f"{self.name.lower().replace('_','-')}"
@dataclass(slots=True, frozen=True)
class Error:
	loc:Loc
	typ:ET
	msg:str
	errors:'ClassVar[list[Error]]' = []
def add_error(err:ET,loc:'Loc',msg:'str') -> None|NoReturn:
	Error.errors.append(Error(loc,err,msg))
	if len(Error.errors) >= 254: 
		# 255s is reserved if there is critical error
		# this branch is here to prevent having >= 256 errors
		# which means you can't sys.exit(len(Error.errors)) meaningfully
		crash_with_errors()
	return None

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

def exit_properly(code:int) -> NoReturn:
	show_errors()
	sys.exit(code)
