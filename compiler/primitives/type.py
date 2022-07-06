from enum import Enum as pythons_enum, auto
from dataclasses import dataclass
import math
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
class Primitive(Type, pythons_enum):
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
			Primitive.VOID : 'i1',
			Primitive.INT  : 'i64',
			Primitive.SHORT: 'i32',
			Primitive.CHAR : 'i8',
			Primitive.BOOL : 'i1',
			Primitive.STR  : '<{ i64, [0 x i8]* }>',
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
@dataclass()#no slots or frozen to simulate a pointer
class Struct(Type):#modifying is allowed only to create recursive data
	name:str
	variables:tuple[tuple[str,Type],...]
	struct_uid:int
	funs:'tuple[tuple[str,Fun,str],...]'
	def __str__(self) -> str:
		return self.name
	def get_magic(self, magic:'str') -> 'tuple[Fun,str]|None':
		for name,fun,llvmid in self.funs:
			if name == f'__{magic}__':
				return fun,llvmid
		return None
	@property
	def llvm(self) -> str:
		return f"%\"struct.{self.struct_uid}.{self.name}\""
@dataclass(slots=True, frozen=True)
class Fun(Type):
	arg_types:tuple[Type, ...]
	return_type:Type
	def __str__(self) -> str:
		return f"({', '.join(f'{arg}' for arg in self.arg_types)}) -> {self.return_type}"
	@property
	def llvm(self) -> str:
		return f"{self.return_type.llvm} ({', '.join(arg.llvm for arg in self.arg_types)})*"
@dataclass(slots=True, frozen=True)
class Module(Type):
	module_uid:'int'
	path:'str'
	def __str__(self) -> str:
		return f"#module({self.path})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException("Module type is not saveable")
@dataclass(slots=True, frozen=True)
class Mix(Type):
	funs:tuple[Type, ...]
	name:str
	def __str__(self) -> str:
		return f"#mix({self.name})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"Mix type is not saveable")

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
@dataclass(slots=True, frozen=True)
class StructKind(Type):
	statics:tuple[tuple[str,Type], ...]
	struct:'Struct'
	@property
	def name(self) -> str:
		return self.struct.name
	@property
	def struct_uid(self) -> int:
		return self.struct.struct_uid
	def __str__(self) -> str:
		return f"#structkind({self.name})"
	@property
	def llvm(self) -> str:
		return f"%\"structkind.{self.struct_uid}.{self.name}\""
	@property
	def llvmid(self) -> str:
		return f"@__structkind.{self.struct_uid}.{self.name}"
@dataclass(slots=True, frozen=True)
class BoundFun(Type):
	fun:'Fun'
	typ:Type
	val:'str'
	@property
	def apparent_typ(self) -> 'Fun':
		return Fun(tuple(i for i in self.fun.arg_types[1:]),self.fun.return_type)
	def __str__(self) -> str:
		return f"#bound_fun({self.typ}, {self.typ})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"bound fun is not saveable")


@dataclass()#no slots or frozen to simulate a pointer
class Enum(Type):#modifying is allowed only to create recursive data
	name:str
	items:tuple[str,...]
	typed_items:tuple[tuple[str,Type],...]
	funs:'tuple[tuple[str,Fun,str],...]'
	enum_uid:int
	@property
	def llvm(self) -> str:
		return f"%\"enum.{self.enum_uid}.{self.name}\""
	def get_magic(self, magic:'str') -> 'tuple[Fun,str]|None':
		for name,fun,llvmid in self.funs:
			if name == f'__{magic}__':
				return fun,llvmid
		return None
	@property
	def llvm_max_item(self) -> str:
		return f"{{{', '.join(typ.llvm for name,typ in self.typed_items)}}}"#FIXME: find a typ that is maximum of the size and use him as 2nd typ (instead of struct of all types)
	@property
	def llvm_item_id(self) -> str:
		length = len(self.items)+len(self.typed_items)
		bits = math.ceil(math.log2(length)) if length != 0 else 1
		return f"i{bits}"
	def __str__(self) -> str:
		return self.name

@dataclass(slots=True, frozen=True)
class EnumKind(Type):
	enum:'Enum'
	@property
	def name(self) -> str:
		return self.enum.name
	@property
	def enum_uid(self) -> int:
		return self.enum.enum_uid
	def __str__(self) -> str:
		return f"#enum_kind({self.name})"
	@property
	def llvm(self) -> str:
		raise NotSaveableException(f"enum kind is not saveable")
	def llvmid_of_type_function(self, idx:int) -> str:
		return f"@\"__enum.{self.enum_uid}.{self.name}.fun_to_create_enum_no.{idx}.{self.enum.typed_items[idx][0]}\""
