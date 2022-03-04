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
	pass
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
@dataclass(frozen=True)
class Ptr(Type):
	pointed:Type
	def __int__(self):
		return 1
	def __str__(self) -> str:
		return f"ptr({self.pointed})"
INT  = Primitive.INT
BOOL = Primitive.BOOL
STR  = Primitive.STR
VOID = Primitive.VOID
PTR  = Primitive.PTR

def find_fun_by_name(ast:'nodes.Tops', name:Token) -> 'nodes.Fun':
	for top in ast.tops:
		if isinstance(top, nodes.Fun):
			if top.name == name:
				return top

	print(f"ERROR: {name.loc}: did not find function '{name}'", file=stderr)
	sys.exit(48)


INTRINSICS_TYPES:'dict[str,tuple[list[Type],Type,int]]' = {
	'len'       : ([STR, ],         INT,  get_id()),
	'ptr'       : ([STR, ],         PTR,  get_id()),
	'str'       : ([INT, PTR],      STR,  get_id()),
	'ptr_to_int': ([PTR, ],         INT,  get_id()),
	'int_to_ptr': ([INT, ],         PTR,  get_id()),
	'save_int'  : ([Ptr(INT), INT], VOID, get_id()),
	'load_int'  : ([Ptr(INT), ],    INT,  get_id()),
	'save_byte' : ([PTR, INT],      VOID, get_id()),
	'load_byte' : ([PTR, ],         INT,  get_id()),
	'syscall0'  : ([INT, ]*1,       INT,  get_id()),
	'syscall1'  : ([INT, ]*2,       INT,  get_id()),
	'syscall2'  : ([INT, ]*3,       INT,  get_id()),
	'syscall3'  : ([INT, ]*4,       INT,  get_id()),
	'syscall4'  : ([INT, ]*5,       INT,  get_id()),
	'syscall5'  : ([INT, ]*6,       INT,  get_id()),
	'syscall6'  : ([INT, ]*7,       INT,  get_id()),

}
