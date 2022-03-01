from enum import Enum, auto
import sys
from sys import stderr

from . import nodes 
from .token import Token
from .core import get_id
__all__ = [
	'Type',
	'find_fun_by_name',
	'INTRINSICS_TYPES',
]

class Type(Enum):
	INT  = auto()
	BOOL = auto()
	STR  = auto()
	VOID = auto()
	PTR  = auto()
	def __int__(self) -> int:
		table:dict[Type, int] = {
			Type.VOID: 0,
			Type.INT : 1,
			Type.BOOL: 1,
			Type.PTR : 1,
			Type.STR : 2,
		}
		assert len(table)==len(Type)
		return table[self]
	def __str__(self) -> str:
		return self.name.lower()


def find_fun_by_name(ast:'nodes.Tops', name:Token) -> 'nodes.Fun':
	for top in ast.tops:
		if isinstance(top, nodes.Fun):
			if top.name == name:
				return top

	print(f"ERROR: {name.loc}: did not find function '{name}'", file=stderr)
	sys.exit(45)


INTRINSICS_TYPES:'dict[str,tuple[list[Type],Type,int]]' = {
	'len'       : ([Type.STR, ],         Type.INT,  get_id()),
	'ptr'       : ([Type.STR, ],         Type.PTR,  get_id()),
	'str'       : ([Type.INT, Type.PTR], Type.STR,  get_id()),
	'ptr_to_int': ([Type.PTR, ],         Type.INT,  get_id()),
	'int_to_ptr': ([Type.INT, ],         Type.PTR,  get_id()),
	'save_int'  : ([Type.PTR, Type.INT], Type.VOID, get_id()),
	'load_int'  : ([Type.PTR, ],         Type.INT,  get_id()),
	'save_byte' : ([Type.PTR, Type.INT], Type.VOID, get_id()),
	'load_byte' : ([Type.PTR, ],         Type.INT,  get_id()),
	'syscall0'  : ([Type.INT, ]*1,       Type.INT,  get_id()),
	'syscall1'  : ([Type.INT, ]*2,       Type.INT,  get_id()),
	'syscall2'  : ([Type.INT, ]*3,       Type.INT,  get_id()),
	'syscall3'  : ([Type.INT, ]*4,       Type.INT,  get_id()),
	'syscall4'  : ([Type.INT, ]*5,       Type.INT,  get_id()),
	'syscall5'  : ([Type.INT, ]*6,       Type.INT,  get_id()),
	'syscall6'  : ([Type.INT, ]*7,       Type.INT,  get_id()),

}
