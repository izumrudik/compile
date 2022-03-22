from enum import Enum, auto
import sys
from sys import stderr
from dataclasses import dataclass

from . import nodes 
from .token import Token
from .core import get_id
__all__ = [
	'Type',
	'Ptr',
	'INT',
	'BOOL',
	'STR',
	'VOID',
	'PTR',
	'find_fun_by_name',
	'INTRINSICS_TYPES',
]
class Type:
	def __int__(self) -> int:
		...
	@property
	def llvm(self) -> str:
		...
class Primitive(Type, Enum):
	INT  = auto()
	BOOL = auto()
	STR  = auto()
	VOID = auto()
	PTR  = auto()
	def __int__(self) -> int:
		table:dict[Type, int] = {
			Primitive.VOID: 0,
			Primitive.INT : 1,
			Primitive.BOOL: 1,
			Primitive.PTR : 1,
			Primitive.STR : 2,
		}
		assert len(table)==len(Primitive)
		return table[self]
	def __str__(self) -> str:
		return self.name.lower()
	@property
	def llvm(self) -> str:
		table:dict[Type, str] = {
			Primitive.VOID: 'void',
			Primitive.INT : 'i64',
			Primitive.BOOL: 'i1',
			Primitive.PTR : 'ptr',
			Primitive.STR : '<{ i64, i8* }>',
		}
		return table[self] 
INT  = Primitive.INT
BOOL = Primitive.BOOL
STR  = Primitive.STR
VOID = Primitive.VOID
PTR  = Primitive.PTR
@dataclass(frozen=True)
class Ptr(Type):
	pointed:Type
	def __int__(self) -> int:
		return 1
	def __str__(self) -> str:
		return f"ptr({self.pointed})"
	@property
	def llvm(self) -> str:
		p = self.pointed.llvm
		if p == 'ptr':
			return "ptr"
		return f"{p}*"
@dataclass(frozen=True)
class StructType(Type):
	struct:'nodes.Struct'
	@property
	def name(self) -> str:
		return self.struct.name.operand
	def __int__(self) -> int:
		return self.struct.sizeof
	def __repr__(self) -> str:
		return self.name
def find_fun_by_name(ast:'nodes.Tops', name:Token) -> 'nodes.Fun':
	for top in ast.tops:
		if isinstance(top, nodes.Fun):
			if top.name == name:
				return top

	print(f"ERROR: {name.loc}: did not find function '{name}'", file=stderr)
	sys.exit(54)


INTRINSICS_TYPES:'dict[str,tuple[list[Type],Type,int]]' = {
	'len'       : ([STR, ],         INT,  get_id()),
	'ptr'       : ([STR, ],         PTR,  get_id()),
	'str'       : ([INT, PTR],      STR,  get_id()),
	'save_int'  : ([Ptr(INT), INT], VOID, get_id()),
	'load_int'  : ([Ptr(INT), ],    INT,  get_id()),
	'save_byte' : ([PTR, INT],      VOID, get_id()),
	'load_byte' : ([PTR, ],         INT,  get_id()),
	'exit'      : ([INT, ],         VOID, get_id()),
	'write'     : ([INT,STR,],      INT,  get_id()),
}
