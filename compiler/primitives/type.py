from enum import Enum, auto
import sys
from sys import stderr

from . import nodes 
from .token import Token
from .core import get_id
__all__ = [
	'Type',
	'find_fun_by_name',
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
	sys.exit(39)
