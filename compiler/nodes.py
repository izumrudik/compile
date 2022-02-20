from abc import ABC
from dataclasses import dataclass,field
from typing import Callable

from .type import Type
from .core import NEWLINE, join, get_id
from .token import TT, Loc, Token
class Node(ABC):
	pass
@dataclass(frozen=True)
class Tops(Node):
	tops:'list[Node]'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{join(self.tops, NEWLINE)}"
@dataclass(frozen=True)
class FunctionCall(Node):
	name:Token
	args:'list[Node|Token]'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.name}({join(self.args)})"
@dataclass(frozen=True)
class TypedVariable(Node):
	name:Token
	typ:'Type'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.name}: {self.typ}"
@dataclass(frozen=True)
class ExprStatement(Node):
	value:'Node | Token'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.value}"
@dataclass(frozen=True)
class Assignment(Node):
	var:'TypedVariable'
	value:'Node|Token'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass(frozen=True)
class ReAssignment(Node):
	name:'Token'
	value:'Node|Token'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.name} = {self.value}"
@dataclass(frozen=True)
class Defining(Node):
	var:'TypedVariable'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.var}"
@dataclass(frozen=True)
class ReferTo(Node):
	name:Token
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
@dataclass(frozen=True)
class IntrinsicConstant(Node):
	name:Token
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
	@property
	def typ(self) -> 'Type':
		if   self.name.operand == 'False': return Type.BOOL
		elif self.name.operand == 'True' : return Type.BOOL
		else:
			assert False, f"Unreachable, unknown {self.name=}"
@dataclass(frozen=True)
class BinaryExpression(Node):
	left:'Token | Node'
	operation:Token
	right:'Token | Node'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"({self.left} {self.operation} {self.right})"
	@property
	def typ(self) -> 'Type':
		if   self.operation == TT.PLUS                  : return Type.INT
		elif self.operation == TT.MINUS                 : return Type.INT
		elif self.operation == TT.ASTERISK              : return Type.INT
		elif self.operation == TT.DOUBLE_SLASH          : return Type.INT
		elif self.operation == TT.PERCENT_SIGN          : return Type.INT
		elif self.operation == TT.LESS_SIGN             : return Type.BOOL
		elif self.operation == TT.GREATER_SIGN          : return Type.BOOL
		elif self.operation == TT.DOUBLE_EQUALS_SIGN    : return Type.BOOL
		elif self.operation == TT.NOT_EQUALS_SIGN       : return Type.BOOL
		elif self.operation == TT.LESS_OR_EQUAL_SIGN    : return Type.BOOL
		elif self.operation == TT.GREATER_OR_EQUAL_SIGN : return Type.BOOL
		elif self.operation.equals(TT.KEYWORD,'or' )    : return Type.BOOL
		elif self.operation.equals(TT.KEYWORD,'xor')    : return Type.BOOL
		elif self.operation.equals(TT.KEYWORD,'and')    : return Type.BOOL
		else:
			assert False, f"Unreachable {self.operation=}"
@dataclass(frozen=True)
class UnaryExpression(Node):
	operation:Token
	right:'Token | Node'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"({self.operation} {self.right})"
	@property
	def typ(self) -> 'Type':
		if self.operation == TT.NOT: return Type.BOOL
		else:
			assert False, f"Unreachable, {self.operation=}"
@dataclass(frozen=True)
class Fun(Node):
	name:Token
	arg_types:'list[TypedVariable]'
	output_type:'Type'
	code:"Code"
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		if len(self.arg_types) > 0:
			return f"fun {self.name} {join(self.arg_types, sep=' ')} -> {self.output_type} {self.code}"
		return f"fun {self.name} -> {self.output_type} {self.code}"
@dataclass(frozen=True)
class Memo(Node):
	name:'Token'
	size:int
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"memo {self.name} {self.size}"
@dataclass(frozen=True)
class Const(Node):
	name:'Token'
	value:int
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"const {self.name} {self.value}"
@dataclass(frozen=True)
class Code(Node):
	statements:'list[Node | Token]'
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		new_line = '\n'
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"{{{tab(new_line+join(self.statements, f'{new_line}'))}{new_line}}}"
@dataclass(frozen=True)
class If(Node):
	loc:'Loc'
	condition:'Node|Token'
	code:'Node'
	else_code:'Node|None' = None
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		if self.else_code is None:
			return f"if {self.condition} {self.code}"
		if isinstance(self.else_code,If):
			return f"if {self.condition} {self.code} el{self.else_code}"

		return f"if {self.condition} {self.code} else {self.else_code}"	
