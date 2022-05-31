from enum import Enum, auto
from dataclasses import dataclass
from typing import Callable, ClassVar, Generator

from . import nodes
__all__ = [
	'Type',
	'NotSaveableException',
]
class NotSaveableException(Exception):
	pass

class Type:
	def __str__(self) -> str:
		...
	def __repr__(self) -> str:
		return str(self)
	@property
	def llvm(self) -> str:
		...
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
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
			Primitive.VOID : 'i2',
			Primitive.INT  : 'i64',
			Primitive.SHORT: 'i32',
			Primitive.CHAR : 'i8',
			Primitive.BOOL : 'i1',
			Primitive.STR  : '<{ i64, i8* }>',
		}
		return table[self]
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return self
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
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return Ptr(self.pointed.fill_generic(d))
@dataclass(slots=True, frozen=True)
class Struct(Type):
	name:'str'
	generics:tuple[Type, ...]
	def __str__(self) -> str:
		if len(self.generics) == 0:
			return self.name
		return f"{self.name}~{', '.join(map(str, self.generics))}~"
	@property
	def llvm(self) -> str:
		return f"%\"struct.{self.name}.{'.'.join(h.llvm for h in self.generics)}\""
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return Struct(self.name, tuple(t.fill_generic(d) for t in self.generics))
@dataclass(slots=True, frozen=True)
class Generic(Type):
	name:'str'
	fills:'ClassVar[dict[Generic,Type]]' = {}
	@staticmethod
	def fill_llvmid(llvm_id:str, fill:'tuple[Type,...]') -> str:
		escape_quotes:Callable[[str],str] = lambda s:s.replace('"', '\\22')
		return f"@\"{escape_quotes(llvm_id)}~{', '.join(i.llvm for i in fill)}~\""
	def __str__(self) -> str:
		return f"%{self.name}"
	@property
	def llvm(self) -> str:
		if self in Generic.fills:
			if self == Generic.fills[self]:
				return VOID.llvm
			return Generic.fills[self].llvm
		raise NotSaveableException(f"Generic type is not saveable")
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		if self in d:
			return d[self]
		return self
@dataclass(slots=True, frozen=True)
class Fun(Type):
	arg_types:tuple[Type, ...]
	return_type:Type
	def __str__(self) -> str:
		return f"({', '.join(f'{arg}' for arg in self.arg_types)}) -> {self.return_type}"
	@property
	def llvm(self) -> str:
		return f"{self.return_type.llvm} ({', '.join(arg.llvm for arg in self.arg_types)})*"
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Fun':
		return Fun(
			tuple(arg.fill_generic(d) for arg in self.arg_types),
			self.return_type.fill_generic(d),
		)
@dataclass(slots=True, frozen=True)
class GenericFun(Type):
	fun:'nodes.Fun'
	@property
	def name(self) -> str:
		return self.fun.name.operand
	def __str__(self) -> str:
		return f"#genericfun({self.name})"
	def llvmid(self,fill:'tuple[Type,...]') -> str:
		return Generic.fill_llvmid(self.fun.llvmid, fill)
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"GenericFun type is not saveable")
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Fun':
		return self.fun.typ.fill_generic(d)
@dataclass(slots=True, frozen=True)
class Module(Type):
	module:'nodes.Module'
	@property
	def path(self) -> str:
		return self.module.path
	def __str__(self) -> str:
		return f"#module({self.path})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException("Module type is not saveable")
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return self
@dataclass(slots=True, frozen=True)
class Mix(Type):
	funs:tuple[Type, ...]
	name:str
	def __str__(self) -> str:
		return f"#mix({self.name})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"Mix type is not saveable")
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return Mix(
			tuple(fun.fill_generic(d) for fun in self.funs),
			self.name,
		)

@dataclass(slots=True, frozen=True)
class Array(Type):
	typ:Type
	size:int = 0
	def __str__(self) -> str:
		if self.size == 0:
			return f"[]{self.typ}"
		return f"[{self.size}]{self.typ}"
	@property
	def llvm(self) -> str:
		return f"[{self.size} x {self.typ.llvm}]"
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return Array(self.typ.fill_generic(d), self.size)
@dataclass(slots=True, frozen=True)
class StructKind(Type):
	struct:'nodes.Struct'
	generics:tuple[Type,...]
	def __str__(self) -> str:
		return f"#structkind({self.name})"
	@property
	def name(self) -> str:
		return self.struct.name.operand
	@property
	def statics(self) -> 'Generator[nodes.TypedVariable, None, None]':
		return (var.var for var in self.struct.static_variables)
	@property
	def llvm(self) -> str:
		return f"%\"structkind.{self.name}.{'.'.join(h.llvm for h in self.generics)}\""
	@property
	def llvmid(self) -> str:
		return Generic.fill_llvmid(f"__structkind.{self.name}", self.generics)
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return StructKind(self.struct, tuple(t.fill_generic(d) for t in self.generics))
@dataclass(slots=True, frozen=True)
class BoundFun(Type):
	fun:'Fun'
	typ:Type
	val:'str'
	@property
	def apparent_typ(self) -> 'Fun':
		return Fun(tuple(i for i in self.fun.arg_types[1:]),self.fun.return_type)
	def __str__(self) -> str:
		return f"bound_fun({self.typ}, {self.typ})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"bound fun is not saveable")
	def fill_generic(self, d:'dict[Generic,Type]') -> 'Type':
		return BoundFun(self.fun.fill_generic(d), self.typ.fill_generic(d), self.val)

