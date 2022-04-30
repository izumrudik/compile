from enum import Enum, auto
import sys
from sys import stderr
from dataclasses import dataclass

from . import nodes
from .token import Token, Loc
from .core import get_id
__all__ = [
	'Type',
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
class Fun(Type):
	arg_types:list[Type]
	return_type:Type
	def __repr__(self) -> str:
		return f"({', '.join(f'{arg}' for arg in self.arg_types)}) -> {self.return_type}"
	@property
	def llvm(self) -> str:
		return f"{self.return_type.llvm} ({', '.join(arg.llvm for arg in self.arg_types)})*"
@dataclass(slots=True, frozen=True)
class Module(Type):
	module:'nodes.Module'
	@property
	def name(self) -> str:
		return self.module.name
	def __repr__(self) -> str:
		return self.name
	@property
	def llvm(self) -> str:
		raise Exception("Module type does not make sense")
@dataclass(slots=True, frozen=True)
class Mix(Type):
	funs:list[Type]
	name:str
	def __repr__(self) -> str:
		return f"mix({self.name})"
	@property
	def llvm(self) -> str:
		raise Exception(f"Mix type does not make sense in llvm, MixTypeTv should be used instead")

@dataclass(slots=True, frozen=True)
class Array(Type):
	size:int
	typ:Type
	def __repr__(self) -> str:
		return f"[{self.size}]{self.typ}"
	@property
	def llvm(self) -> str:
		return f"[{self.size} x {self.typ.llvm}]"
