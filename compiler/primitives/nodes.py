from abc import ABC
from dataclasses import dataclass, field
from typing import Callable
from sys import stderr
import sys
from .type import Type
from . import type as types
from .core import NEWLINE, get_id
from .token import TT, Loc, Token
class Node(ABC):
	uid:int
	def __eq__(self, __o: object) -> bool:
		if isinstance(__o, Node):
			return self.uid == __o.uid
		return NotImplemented
@dataclass(slots=True, frozen=True)
class Module(Node):
	tops:tuple[Node, ...]
	path:str
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{NEWLINE.join([str(i) for i in self.tops])}"
@dataclass(slots=True, frozen=True)
class Import(Node):
	path:str
	name:str
	module:Module
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"import {self.path}"
@dataclass(slots=True, frozen=True)
class FromImport(Node):
	path:str
	name:str
	module:Module
	imported_names:tuple[str, ...]
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"from {self.path} import {', '.join(self.imported_names)}"
@dataclass(slots=True, frozen=True)
class Call(Node):
	loc:Loc
	func:Node|Token
	args:tuple[Node|Token, ...]
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.func}({', '.join([str(i) for i in self.args])})"
@dataclass(slots=True, frozen=True)
class TypedVariable(Node):
	name:Token
	typ:Type
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}: {self.typ}"
@dataclass(slots=True, frozen=True)
class ExprStatement(Node):
	value:Node | Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.value}"
@dataclass(slots=True, frozen=True)
class Assignment(Node):
	var:TypedVariable
	value:Node|Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass(slots=True, frozen=True)
class Alias(Node):
	name:'Token'
	value:'Token|Node'
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"alias {self.name} = {self.value}"
@dataclass(slots=True, frozen=True)
class Use(Node):
	name:Token
	arg_types:tuple[Type, ...]
	return_type:Type
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"use {self.name}({', '.join(str(i) for i in self.arg_types)}) -> {self.return_type}"
@dataclass(slots=True, frozen=True)
class Save(Node):
	space:Node|Token
	value:Node|Token
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.space} = {self.value}"
@dataclass(slots=True,frozen=True)
class VariableSave(Node):
	space:Token
	value:Node|Token
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.space} = {self.value}"
@dataclass(slots=True, frozen=True)
class Declaration(Node):
	var:TypedVariable
	times:'Node|Token|None' = None
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.times is None:
			return f"{self.var}"
		return f"[{self.times}]{self.var}"
@dataclass(slots=True, frozen=True)
class ReferTo(Node):
	name:Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
@dataclass(slots=True, frozen=True)
class Constant(Node):
	name:Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
	@property
	def typ(self) -> 'Type':
		if   self.name.operand == 'False': return types.BOOL
		elif self.name.operand == 'True' : return types.BOOL
		elif self.name.operand == 'Null' : return types.Ptr(types.VOID)
		elif self.name.operand == 'Argv' : return types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))) #ptr([]ptr([]char))
		elif self.name.operand == 'Argc' : return types.INT
		elif self.name.operand == 'Void' : return types.VOID
		else:
			assert False, f"Unreachable, unknown {self.name=}"
@dataclass(slots=True, frozen=True)
class BinaryExpression(Node):
	left:Token | Node
	operation:Token
	right:Token | Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.left} {self.operation} {self.right})"
	def typ(self,left:Type,right:Type) -> 'Type':
		op = self.operation
		lr = left, right

		issamenumber = (
					(left == right == types.INT)   or 
					(left == right == types.SHORT) or 
					(left == right == types.CHAR)
				)
		isptr = (
			isinstance(left,types.Ptr) and
			isinstance(right,types.Ptr)
		)
		if   op == TT.PLUS                  and issamenumber: return left
		elif op == TT.MINUS                 and issamenumber: return left
		elif op == TT.ASTERISK              and issamenumber: return left
		elif op == TT.DOUBLE_SLASH          and issamenumber: return left
		elif op == TT.PERCENT          and issamenumber: return left
		elif op == TT.DOUBLE_LESS      and issamenumber: return left
		elif op == TT.DOUBLE_GREATER   and issamenumber: return left
		elif op.equals(TT.KEYWORD, 'or' )   and issamenumber: return left
		elif op.equals(TT.KEYWORD, 'xor')   and issamenumber: return left
		elif op.equals(TT.KEYWORD, 'and')   and issamenumber: return left
		elif op == TT.LESS             and issamenumber: return types.BOOL
		elif op == TT.GREATER          and issamenumber: return types.BOOL
		elif op == TT.DOUBLE_EQUALS    and issamenumber: return types.BOOL
		elif op == TT.NOT_EQUALS       and issamenumber: return types.BOOL
		elif op == TT.LESS_OR_EQUAL    and issamenumber: return types.BOOL
		elif op == TT.GREATER_OR_EQUAL and issamenumber: return types.BOOL
		elif op.equals(TT.KEYWORD, 'or' ) and lr == (types.BOOL, types.BOOL): return types.BOOL
		elif op.equals(TT.KEYWORD, 'xor') and lr == (types.BOOL, types.BOOL): return types.BOOL
		elif op.equals(TT.KEYWORD, 'and') and lr == (types.BOOL, types.BOOL): return types.BOOL
		elif op == TT.DOUBLE_EQUALS and isptr:return types.BOOL
		elif op == TT.NOT_EQUALS and isptr: return types.BOOL
		else:
			print(f"ERROR: {self.operation.loc} unsupported operation '{self.operation}' for '{left}' and '{right}'", file=stderr)
			sys.exit(89)
@dataclass(slots=True, frozen=True)
class UnaryExpression(Node):
	operation:Token
	left:Token | Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.operation}{self.left})"
	def typ(self,left:Type) -> 'Type':
		op = self.operation
		l = left
		if op == TT.NOT and l == types.BOOL : return types.BOOL
		if op == TT.NOT and l == types.INT  : return types.INT
		if op == TT.NOT and l == types.SHORT: return types.SHORT
		if op == TT.NOT and l == types.CHAR : return types.CHAR
		if op == TT.AT and isinstance(l,types.Ptr): return l.pointed
		else:
			print(f"ERROR: {self.operation.loc} unsupported operation '{self.operation}' for '{left}'", file=stderr)
			sys.exit(90)
@dataclass(slots=True, frozen=True)
class Dot(Node):
	origin:Node|Token
	access:Token
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.origin}.{self.access}"
	def lookup_struct(self,struct:'Struct') -> 'tuple[int, Type]|Fun':
		for idx,var in enumerate(struct.variables):
			if var.name == self.access:
				return idx,var.typ
		for idx, fun in enumerate(struct.funs):
			if fun.name == self.access:
				return fun
		print(f"ERROR: {self.access.loc} did not found field '{self.access}' of struct '{self.origin}'", file=stderr)
		sys.exit(91)
	def lookup_struct_kind(self, struct:'types.StructKind') -> 'tuple[int,Type]':
		for idx,var in enumerate(struct.statics):
			if var.name == self.access:
				return idx,var.typ
		for idx,fun in enumerate(struct.struct.funs):
			if fun.name == self.access:
				return len(struct.struct.static_variables)+idx,fun.typ
		print(f"ERROR: {self.access.loc} did not found field '{self.access}' of struct kind '{self.origin}'", file=stderr)
		sys.exit(92)

@dataclass(slots=True, frozen=True)
class GetItem(Node):
	origin:Node|Token
	subscript:Node|Token
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.origin}[{self.subscript}]"
@dataclass(slots=True, frozen=True)
class Fun(Node):
	name:Token
	arg_types:tuple[TypedVariable, ...]
	return_type:Type
	code:'Code'
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if len(self.arg_types) > 0:
			return f"fun {self.name} {' '.join([str(i) for i in self.arg_types])} -> {self.return_type} {self.code}"
		return f"fun {self.name} -> {self.return_type} {self.code}"
	@property
	def typ(self) -> 'types.Fun':
		return types.Fun(tuple(arg.typ for arg in self.arg_types), self.return_type)
	@property
	def llvmid(self) -> 'str':
		return f"@{self.name.operand}"

@dataclass(slots=True, frozen=True)
class Mix(Node):
	loc:Loc
	name:Token
	funs:tuple[ReferTo, ...]
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"mix {self.name} {{{tab(NEWLINE+NEWLINE.join(fun.name.operand for fun in self.funs))}{NEWLINE}}}"
@dataclass(slots=True, frozen=True)
class Const(Node):
	name:Token
	value:int
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"const {self.name} {self.value}"
@dataclass(slots=True, frozen=True)
class Code(Node):
	statements:tuple[Node | Token, ...]
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"{{{tab(NEWLINE+NEWLINE.join([str(i) for i in self.statements]))}{NEWLINE}}}"
@dataclass(slots=True, frozen=True)
class If(Node):
	loc:Loc
	condition:Node|Token
	code:Node
	else_code:Node|None = None
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.else_code is None:
			return f"if {self.condition} {self.code}"
		if isinstance(self.else_code, If):
			return f"if {self.condition} {self.code} el{self.else_code}"

		return f"if {self.condition} {self.code} else {self.else_code}"

@dataclass(slots=True, frozen=True)
class Return(Node):
	loc:Loc
	value:Node|Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"return {self.value}"
@dataclass(slots=True, frozen=True)
class While(Node):
	loc:Loc
	condition:Node|Token
	code:Code
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"while {self.condition} {self.code}"
@dataclass(slots=True, frozen=True)
class Struct(Node):
	loc:Loc
	name:Token
	variables:tuple[TypedVariable, ...]
	static_variables:tuple[Assignment, ...]
	funs:tuple[Fun, ...]
	generics:tuple[types.Generic, ...]
	generic_fills:set[tuple[Type, ...]] = field(default_factory=set, compare=False, repr=False) # filled at type checking
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"struct {self.name}<{', '.join(map(str,self.generics))}> {{{tab(NEWLINE+NEWLINE.join([str(i) for i in self.variables]+[str(i) for i in self.static_variables]+[str(i) for i in self.funs]))}{NEWLINE}}}"
@dataclass(slots=True, frozen=True)
class Cast(Node):
	loc:Loc
	typ:Type
	value:Node|Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"${self.typ}({self.value})"
@dataclass(slots=True, frozen=True)
class StrCast(Node):
	loc:Loc
	length:Node|Token
	pointer:Node|Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"$({self.length}, {self.pointer})"
