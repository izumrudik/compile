from abc import ABC
from dataclasses import dataclass, field
from typing import Callable
from .type import Type
from . import type as types
from .core import NEWLINE, get_id, critical_error, ET, Loc
from .token import TT, Token
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
	@property
	def llvmid(self) -> str:
		return f"@.setup_module.{self.uid}"
	def str_llvmid(self,idx:int) -> str:
		return f"@.str.{self.uid}.{idx}"
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
	func:Node
	args:tuple[Node, ...]
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
	value:Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.value}"
@dataclass(slots=True, frozen=True)
class Assignment(Node):
	var:TypedVariable
	value:Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass(slots=True, frozen=True)
class Alias(Node):
	name:'Token'
	value:'Node'
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"set {self.name} = {self.value}"
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
	space:Node
	value:Node
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.space} = {self.value}"
@dataclass(slots=True, frozen=True)
class VariableSave(Node):
	space:Token
	value:Node
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.space} = {self.value}"
@dataclass(slots=True, frozen=True)
class Declaration(Node):
	var:TypedVariable
	times:'Node|None' = None
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.times is None:
			return f"{self.var}"
		return f"[{self.times}]{self.var}"
@dataclass(slots=True, frozen=True)
class ReferTo(Node):
	name:Token
	generics:tuple[Type,...]
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if len(self.generics) == 0:
			return f"{self.name}"
		return f"{self.name}<{', '.join(map(str,self.generics))}>"
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
		elif self.name.operand == 'Argv' : return types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))) #ptr([]ptr([]char))
		elif self.name.operand == 'Argc' : return types.INT
		elif self.name.operand == 'Void' : return types.VOID
		else:
			assert False, f"Unreachable, unknown {self.name=}"
@dataclass(slots=True, frozen=True)
class BinaryExpression(Node):
	left:Node
	operation:Token
	right:Node
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
			critical_error(ET.BIN_OP, self.operation.loc, f"Unsupported binary operation '{self.operation}' for '{left}' and '{right}'")
@dataclass(slots=True, frozen=True)
class UnaryExpression(Node):
	operation:Token
	left:Node
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
			critical_error(ET.UNARY_OP, self.operation.loc, f"Unsupported unary operation '{self.operation}' for '{left}'")
@dataclass(slots=True, frozen=True)
class Dot(Node):
	origin:Node
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
		critical_error(ET.DOT_STRUCT, self.access.loc, f"did not found field '{self.access}' of struct '{self.origin}'")
	def lookup_struct_kind(self, struct:'types.StructKind') -> 'tuple[int,Type]':
		for idx,var in enumerate(struct.statics):
			if var.name == self.access:
				return idx,var.typ
		for idx,fun in enumerate(struct.struct.funs):
			if fun.name == self.access:
				return len(struct.struct.static_variables)+idx,fun.typ
		critical_error(ET.DOT_STRUCT_KIND, self.access.loc, f"did not found field '{self.access}' of struct kind '{self.origin}'")


@dataclass(slots=True, frozen=True)
class Subscript(Node):
	origin:Node
	subscript:Node
	loc:Loc
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.origin}[{self.subscript}]"
@dataclass(slots=True, frozen=True)
class Fun(Node):
	name:Token
	generics:tuple[types.Generic, ...]
	arg_types:tuple[TypedVariable, ...]
	return_type:Type
	code:'Code'
	generic_fills:set[tuple[Type, ...]] = field(default_factory=set, compare=False, repr=False) # filled at type checking
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		prefix = f'fun {self.name}'
		if len(self.generics)>0:
			prefix+=f"~{', '.join(map(str,self.generics))}~"
		if len(self.arg_types) > 0:
			return f"{prefix} {' '.join([str(i) for i in self.arg_types])} -> {self.return_type} {self.code}"
		return f"{prefix} -> {self.return_type} {self.code}"
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
	statements:tuple[Node, ...]
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"{{{tab(NEWLINE+NEWLINE.join([str(i) for i in self.statements]))}{NEWLINE}}}"
@dataclass(slots=True, frozen=True)
class If(Node):
	loc:Loc
	condition:Node
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
	value:Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"return {self.value}"
@dataclass(slots=True, frozen=True)
class While(Node):
	loc:Loc
	condition:Node
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
	def get_magic(self, magic:'str', loc:Loc) -> Fun:
		for fun in self.funs:
			if fun.name.operand == f'__{magic}__':
				return fun
		critical_error(ET.MAGIC, loc, f"structure '{self.name}' has no '__{magic}__' magic defined")
@dataclass(slots=True, frozen=True)
class Cast(Node):
	loc:Loc
	typ:Type
	value:Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"${self.typ}({self.value})"
@dataclass(slots=True, frozen=True)
class StrCast(Node):
	loc:Loc
	length:Node
	pointer:Node
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"$({self.length}, {self.pointer})"

@dataclass(slots=True, frozen=True)
class Str(Node):
	token:Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"\"{self.token.operand}\""
@dataclass(slots=True, frozen=True)
class Int(Node):
	token:Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.token.operand}"
@dataclass(slots=True, frozen=True)
class Short(Node):
	token:Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.token.operand}s"
@dataclass(slots=True, frozen=True)
class Char(Node):
	token:Token
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{ord(self.token.operand)}c"

@dataclass(slots=True, frozen=True)
class Template(Node):
	formatter:Node
	strings:tuple[Token, ...]
	values:tuple[Node, ...]
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	@property
	def loc(self) -> Loc:
		assert len(self.strings) > 0, "template has no strings"
		return self.strings[0].loc
	def __str__(self) -> str:
		assert len(self.strings) - len(self.values) == 1, "template is corrupted"
		out = f"{self.formatter}`{self.strings[0].operand}"
		for idx, val in enumerate(self.values):
			out += f"{{{val}}}{self.strings[idx+1].operand}"
		return out + '`'
