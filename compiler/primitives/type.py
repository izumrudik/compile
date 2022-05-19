from enum import Enum, auto
from dataclasses import dataclass
from typing import Generator

from numpy import generic
from . import nodes
__all__ = [
	'Type',
	'NotSaveableException',
]
class NotSaveableException(Exception):
	pass

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
		return f"*{self.pointed}"
	@property
	def llvm(self) -> str:
		p = self.pointed.llvm
		if p == 'ptr':
			return "ptr"
		if p == 'void':
			return 'i8*'
		return f"{p}*"
@dataclass(slots=True, frozen=True)
class Struct(Type):
	name:'str'
	generics:list[Type]
	def __repr__(self) -> str:
		if len(self.generics) == 0:
			return self.name
		return f"{self.name}<{', '.join(map(str, self.generics))}>"
	@property
	def llvm(self) -> str:
		if len(self.generics) == 0:
			return f"%struct.{self.name}"
		return f"%\"struct.{self.name}.{self.generics}\""
@dataclass(slots=True, frozen=True)
class Generic(Type):
	name:'str'
	def __repr__(self) -> str:
		return f"%{self.name}"
	@property
	def llvm(self) -> str:
		return f"<Generic type spilled '{self.name}'>"
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
	def path(self) -> str:
		return self.module.path
	def __repr__(self) -> str:
		return f"#module({self.path})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException("Module type does not make sense")
@dataclass(slots=True, frozen=True)
class Mix(Type):
	funs:list[Type]
	name:str
	def __repr__(self) -> str:
		return f"#mix({self.name})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"Mix type does not make sense in llvm, MixTypeTv should be used instead")

@dataclass(slots=True, frozen=True)
class Array(Type):
	size:int
	typ:Type
	def __repr__(self) -> str:
		return f"[{self.size}]{self.typ}"
	@property
	def llvm(self) -> str:
		return f"[{self.size} x {self.typ.llvm}]"
@dataclass(slots=True, frozen=True)
class StructKind(Type):
	struct:'nodes.Struct'
	def __repr__(self) -> str:
		return f"#structkind({self.name})"
	@property
	def name(self) -> str:
		return self.struct.name.operand
	@property
	def statics(self) -> 'Generator[nodes.TypedVariable, None, None]':
		return (var.var for var in self.struct.static_variables)
	@property
	def llvm(self) -> str:
		return f"{{{', '.join([i.typ.llvm for i in self.statics]+[i.typ.llvm for i in self.struct.funs])}}}"

@dataclass(slots=True, frozen=True)
class BoundFun(Type):
	fun:'nodes.Fun'
	typ:Type
	val:'str'
	def __repr__(self) -> str:
		return f"bound_fun({self.typ}, {self.fun.typ})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"bound type does not make sense in llvm")
	@property
	def apparent_typ(self) -> 'Fun':
		return Fun([i.typ for i in self.fun.arg_types[1:]],self.fun.return_type)

