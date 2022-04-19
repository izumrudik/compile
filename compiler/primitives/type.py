from enum import Enum, auto
import sys
from sys import stderr
from dataclasses import dataclass

from . import nodes
from .token import Token
from .core import get_id
__all__ = [
	'Type',
	'find_fun_by_name',
	'INTRINSICS_TYPES'
]
class Type:
	def __int__(self) -> int:
		...
	@property
	def llvm(self) -> str:
		...
class Primitive(Type, Enum):
	INT   = auto()
	STR   = auto()
	BOOL  = auto()
	VOID  = auto()
	CHAR  = auto()
	SHORT = auto()
	def __str__(self) -> str:
		return self.name.lower()
	@property
	def llvm(self) -> str:
		table:dict[Type, str] = {
			Primitive.VOID : 'void',
			Primitive.INT  : 'i64',
			Primitive.SHORT: 'i32',
			Primitive.CHAR : 'i8',
			Primitive.BOOL : 'i1',
			Primitive.STR  : '<{ i64, i8* }>',
		}
		return table[self]
INT   = Primitive.INT
BOOL  = Primitive.BOOL
STR   = Primitive.STR
VOID  = Primitive.VOID
CHAR  = Primitive.CHAR
SHORT = Primitive.SHORT
@dataclass(slots=True, frozen=True)
class Ptr(Type):
	pointed:Type
	def __str__(self) -> str:
		return f"ptr({self.pointed})"
	@property
	def llvm(self) -> str:
		p = self.pointed.llvm
		if p == 'ptr':
			return "ptr"
		return f"{p}*"
@dataclass(slots=True, frozen=True)
class Struct(Type):
	struct:'nodes.Struct'
	@property
	def name(self) -> str:
		return self.struct.name.operand
	def __repr__(self) -> str:
		return self.name
	@property
	def llvm(self) -> str:
		return f"%struct.{self.struct.name}"
@dataclass(slots=True, frozen=True)
class Array(Type):
	size:int
	typ:Type
	def __repr__(self) -> str:
		return f"[{self.size}]{self.typ}"
	@property
	def llvm(self) -> str:
		return f"[{self.size} x {self.typ.llvm}]"
def find_fun_by_name(ast:'nodes.Tops', name:Token, actual_types:list[Type]) -> 'tuple[list[Type],Type,str]':
	intrinsic = INTRINSICS_TYPES.get(name.operand)
	if intrinsic is not None:
		input_types, output_type, _ = intrinsic
		return input_types, output_type, f"@{name.operand}_"
	for top in ast.tops:
		if isinstance(top, nodes.Fun):
			if top.name == name:
				return [var.typ for var in top.arg_types], top.return_type, f"@{top.name}"
		if isinstance(top, nodes.Use):
			if top.name == name:
				return top.arg_types, top.return_type, f"@{top.name}"
		if isinstance(top, nodes.Mix):
			if top.name == name:
				for fun_name in top.funs:
					arg_types,return_type,llvm_name = find_fun_by_name(ast,fun_name,actual_types)
					if len(actual_types) != len(arg_types):
						continue#continue searching
					for actual_arg,arg in zip(actual_types,arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return arg_types,return_type,llvm_name#found fun
					continue
				print(f"ERROR: {name.loc} did not find function to match {tuple(actual_types)!s} in mix '{name}'", file=stderr)
				sys.exit(80)
				
	print(f"ERROR: {name.loc} did not find function/overload '{name}'", file=stderr)
	sys.exit(81)


INTRINSICS_TYPES:'dict[str,tuple[list[Type],Type,int]]' = {
	'len'       : ([STR],               INT,  get_id()),
	'ptr'       : ([STR],         Ptr(CHAR),  get_id()),
	'str'       : ([INT, Ptr(CHAR)],    STR,  get_id()),
}
