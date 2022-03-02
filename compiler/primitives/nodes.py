from abc import ABC
from dataclasses import dataclass, field
from typing import Callable
from sys import stderr
import sys
from .type import Type, Ptr, INT, BOOL, STR, VOID, PTR
from .core import NEWLINE, get_id
from .token import TT, Loc, Token
class Node(ABC):
	pass
@dataclass(frozen=True)
class Tops(Node):
	tops:'list[Node]'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{NEWLINE.join([str(i) for i in self.tops])}"
@dataclass(frozen=True)
class FunctionCall(Node):
	name:Token
	args:'list[Node|Token]'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}({', '.join([str(i) for i in self.args])})"
@dataclass(frozen=True)
class TypedVariable(Node):
	name:Token
	typ:'Type'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}: {self.typ}"
@dataclass(frozen=True)
class ExprStatement(Node):
	value:'Node | Token'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.value}"
@dataclass(frozen=True)
class Assignment(Node):
	var:'TypedVariable'
	value:'Node|Token'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass(frozen=True)
class ReAssignment(Node):
	name:'Token'
	value:'Node|Token'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name} = {self.value}"
@dataclass(frozen=True)
class Defining(Node):
	var:'TypedVariable'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.var}"
@dataclass(frozen=True)
class ReferTo(Node):
	name:Token
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
@dataclass(frozen=True)
class IntrinsicConstant(Node):
	name:Token
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
	@property
	def typ(self) -> 'Type':
		if   self.name.operand == 'False': return BOOL
		elif self.name.operand == 'True' : return BOOL
		else:
			assert False, f"Unreachable, unknown {self.name=}"
@dataclass(frozen=True)
class BinaryExpression(Node):
	left:'Token | Node'
	operation:Token
	right:'Token | Node'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.left} {self.operation} {self.right})"
	def typ(self,left:Type,right:Type) -> 'Type':
		op = self.operation
		lr = left, right
		if   op == TT.PLUS                  and lr == (INT, INT): return INT
		elif op == TT.PLUS                  and lr == (PTR, INT): return PTR
		elif op == TT.MINUS                 and lr == (INT, INT): return INT
		elif op == TT.ASTERISK              and lr == (INT, INT): return INT
		elif op == TT.DOUBLE_SLASH          and lr == (INT, INT): return INT
		elif op == TT.PERCENT_SIGN          and lr == (INT, INT): return INT
		elif op == TT.LESS_SIGN             and lr == (INT, INT): return BOOL
		elif op == TT.GREATER_SIGN          and lr == (INT, INT): return BOOL
		elif op == TT.DOUBLE_LESS_SIGN      and lr == (INT, INT): return INT 
		elif op == TT.DOUBLE_GREATER_SIGN   and lr == (INT, INT): return INT 
		elif op == TT.DOUBLE_EQUALS_SIGN    and lr == (INT, INT): return BOOL
		elif op == TT.NOT_EQUALS_SIGN       and lr == (INT, INT): return BOOL
		elif op == TT.LESS_OR_EQUAL_SIGN    and lr == (INT, INT): return BOOL
		elif op == TT.GREATER_OR_EQUAL_SIGN and lr == (INT, INT): return BOOL
		elif op.equals(TT.KEYWORD, 'or' ) and lr == (BOOL, BOOL): return BOOL
		elif op.equals(TT.KEYWORD, 'xor') and lr == (BOOL, BOOL): return BOOL
		elif op.equals(TT.KEYWORD, 'and') and lr == (BOOL, BOOL): return BOOL
		elif op.equals(TT.KEYWORD, 'or' ) and lr == (INT,  INT ): return INT 
		elif op.equals(TT.KEYWORD, 'xor') and lr == (INT,  INT ): return INT 
		elif op.equals(TT.KEYWORD, 'and') and lr == (INT,  INT ): return INT 
		else:
			print(f"ERROR: {self.operation.loc}: unsupported operation '{self.operation}' for '{left}' and '{right}'", file=stderr)
			sys.exit(40)
@dataclass(frozen=True)
class UnaryExpression(Node):
	operation:Token
	right:'Token | Node'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.operation} {self.right})"
	@property
	def typ(self) -> 'Type':
		if self.operation == TT.NOT: return BOOL
		else:
			assert False, f"Unreachable, {self.operation=}"
@dataclass(frozen=True)
class Fun(Node):
	name:Token
	arg_types:'list[TypedVariable]'
	output_type:'Type'
	code:"Code"
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		prefix = f""
		if len(self.arg_types) > 0:
			return f"{prefix}fun {self.name} {' '.join([str(i) for i in self.arg_types])} -> {self.output_type} {self.code}"
		return f"{prefix}fun {self.name} -> {self.output_type} {self.code}"
@dataclass(frozen=True)
class Memo(Node):
	name:'Token'
	size:int
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"memo {self.name} {self.size}"
@dataclass(frozen=True)
class Const(Node):
	name:'Token'
	value:int
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"const {self.name} {self.value}"
@dataclass(frozen=True)
class Code(Node):
	statements:'list[Node | Token]'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"{{{tab(NEWLINE+NEWLINE.join([str(i) for i in self.statements]))}{NEWLINE}}}"
@dataclass(frozen=True)
class If(Node):
	loc:Loc
	condition:'Node|Token'
	code:'Node'
	else_code:'Node|None' = None
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.else_code is None:
			return f"if {self.condition} {self.code}"
		if isinstance(self.else_code, If):
			return f"if {self.condition} {self.code} el{self.else_code}"

		return f"if {self.condition} {self.code} else {self.else_code}"	

@dataclass(frozen=True)
class Return(Node):
	loc:Loc
	value:'Node|Token'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"return {self.value}"
@dataclass(frozen=True)
class While(Node):
	loc:Loc
	condition:'Node|Token'
	code:'Code'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"while {self.condition} {self.code}"
@dataclass(frozen=True)
class Struct(Node):
	loc:Loc
	name:Token
	variables:'list[TypedVariable]'
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"struct {self.name} {{{tab(NEWLINE+NEWLINE.join([str(i) for i in self.variables]))}{NEWLINE}}}"
	@property
	def names(self) -> 'dict[str,int]':
		base = self.name.operand
		d:'dict[str,int]' =  {}
		offset = 0
		for var in self.variables:
			d[f"{base}.{var.name}"] = offset
			offset += 8*int(var.typ)
		d[f"sizeof[{base}]"] = offset
		return d
