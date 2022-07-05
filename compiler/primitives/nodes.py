from abc import ABC
from dataclasses import dataclass, field
from typing import Callable, Iterable
from .type import Type
from . import type as types
from .core import NEWLINE, Config, Place, escape, get_id, ET
from .token import TT, Token

@dataclass(slots=True, frozen=True)
class Module:
	tops:'tuple[Node, ...]'
	path:str
	builtin_module:'Module|None'
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{NEWLINE.join(str(i) for i in self.tops)}"
	@property
	def llvmid(self) -> str:
		return f"@.setup_module.{self.uid}"
	def str_llvmid(self,idx:int) -> str:
		return f"@.str.{self.uid}.{idx}"

class Node(ABC):
	place:Place
	uid:int
	def __eq__(self, __o: object) -> bool:
		if isinstance(__o, Node):
			return self.uid == __o.uid
		return NotImplemented
@dataclass(slots=True, frozen=True)
class Import(Node):
	path:str
	path_place:Place
	name:str
	module:Module
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"import {self.path}"
@dataclass(slots=True, frozen=True)
class FromImport(Node):
	path:str
	path_place:Place
	module:Module
	imported_names:tuple[Token, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"from {self.path} import {', '.join(map(str,self.imported_names))}"
@dataclass(slots=True, frozen=True)
class Call(Node):
	func:Node
	args:tuple[Node, ...]
	call_place:Place
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.func}({', '.join([str(i) for i in self.args])})"
@dataclass(slots=True, frozen=True)
class TypedVariable(Node):
	name:Token
	typ:'Node'
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}: {self.typ}"
@dataclass(slots=True, frozen=True)
class ExprStatement(Node):
	value:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.value}"
@dataclass(slots=True, frozen=True)
class Assignment(Node):# a:b = c
	var:TypedVariable
	value:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass(slots=True, frozen=True)
class Set(Node):
	name:'Token'
	value:'Node'
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"set {self.name} = {self.value}"
@dataclass(slots=True, frozen=True)
class Use(Node):
	arg_types:'tuple[Node, ...]'
	return_type:'Node'
	as_name:Token
	name:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		suffix = ''
		if self.as_name is self.name:
			suffix+=f' as {self.as_name}'
		return f"use {self.name}({', '.join(str(i) for i in self.arg_types)}) -> {self.return_type}{suffix}"
@dataclass(slots=True, frozen=True)
class Save(Node):
	space:Node
	value:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.space} = {self.value}"
@dataclass(slots=True, frozen=True)
class VariableSave(Node):
	space:Token
	value:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.space} = {self.value}"
@dataclass(slots=True, frozen=True)
class Declaration(Node):
	var:TypedVariable
	times:'Node|None'
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.times is None:
			return f"{self.var}"
		return f"[{self.times}]{self.var}"
@dataclass(slots=True, frozen=True)
class ReferTo(Node):
	name:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
@dataclass(slots=True, frozen=True)
class Constant(Node):
	name:Token
	place:Place
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
class BinaryOperation(Node):
	left:Node
	operation:Token
	right:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.left} {self.operation} {self.right})"
	def typ(self,left:Type,right:Type, config:'Config') -> 'Type':
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
		is_enum = (
			isinstance(left,types.Enum) and
			isinstance(right,types.Enum)
		)
		if   op == TT.PLUS                  and issamenumber: return left
		elif op == TT.MINUS                 and issamenumber: return left
		elif op == TT.ASTERISK              and issamenumber: return left
		elif op == TT.DOUBLE_SLASH          and issamenumber: return left
		elif op == TT.PERCENT               and issamenumber: return left
		elif op == TT.DOUBLE_LESS           and issamenumber: return left
		elif op == TT.DOUBLE_GREATER        and issamenumber: return left
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
		elif op == TT.DOUBLE_EQUALS and (isptr or is_enum): return types.BOOL
		elif op == TT.NOT_EQUALS    and (isptr or is_enum): return types.BOOL
		elif op == TT.ASTERISK and lr == (types.STR, types.INT): return types.STR
		else:
			config.errors.critical_error(ET.BIN_OP, self.operation.place, f"Unsupported binary operation '{self.operation}' for '{left}' and '{right}'")
@dataclass(slots=True, frozen=True)
class UnaryExpression(Node):
	operation:Token
	left:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.operation}{self.left})"
	def typ(self,left:Type,config:Config) -> 'Type':
		op = self.operation
		l = left
		if op == TT.NOT and l == types.BOOL : return types.BOOL
		if op == TT.NOT and l == types.INT  : return types.INT
		if op == TT.NOT and l == types.SHORT: return types.SHORT
		if op == TT.NOT and l == types.CHAR : return types.CHAR
		if op == TT.AT and isinstance(l,types.Ptr): return l.pointed
		else:
			config.errors.critical_error(ET.UNARY_OP, self.operation.place, f"Unsupported unary operation '{self.operation}' for '{left}'")
@dataclass(slots=True, frozen=True)
class Dot(Node):
	origin:Node
	access:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.origin}.{self.access}"
	def lookup_struct(self,struct:'types.Struct', config:Config) -> 'tuple[int, Type]|tuple[types.Fun,str]':
		for idx,(name,typ) in enumerate(struct.variables):
			if name == self.access.operand:
				return idx,typ
		for idx, (name,fun,llvmid) in enumerate(struct.funs):
			if name == self.access.operand:
				return fun,llvmid
		config.errors.critical_error(ET.DOT_STRUCT, self.access.place, f"did not found field '{self.access}' of struct '{struct.name}'")
	def lookup_struct_kind(self, struct:'types.StructKind', config:Config) -> 'tuple[int,Type]':
		for idx,(name, typ) in enumerate(struct.statics):
			if name == self.access.operand:
				return idx,typ
		config.errors.critical_error(ET.DOT_STRUCT_KIND, self.access.place, f"did not found field '{self.access}' of struct kind '{struct.name}'")
	def lookup_enum_kind(self, enum:'types.EnumKind', config:Config) -> tuple[int,types.Fun|types.Enum]:
		for idx,(name, typ) in enumerate(enum.enum.typed_items):
			if name == self.access.operand:
				return idx,types.Fun((typ,), enum.enum)
		for idx,name in enumerate(enum.enum.items):
			if name == self.access.operand:
				return idx,enum.enum
		config.errors.critical_error(ET.DOT_ENUM_KIND, self.access.place, f"did not found item '{self.access}' of enum '{enum.name}'")


@dataclass(slots=True, frozen=True)
class Subscript(Node):
	origin:Node
	subscripts:tuple[Node, ...]
	access_place:Place
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.origin}[{', '.join(map(str,self.subscripts))}]"
@dataclass(slots=True, frozen=True)
class Fun(Node):
	name:Token
	arg_types:tuple[TypedVariable, ...]
	return_type:'Node|None'
	code:'Code'
	args_place:Place
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		prefix = f'fun {self.name}'
		return f"{prefix}({', '.join([str(i) for i in self.arg_types])}) -> {self.return_type} {self.code}"
	@property
	def llvmid(self) -> 'str':
		return f'@"function.{self.name.operand}.{self.uid}"'
	@property
	def return_type_place(self) -> 'Place':
		return self.return_type.place if self.return_type is not None else self.name.place
	def typ(self, unwrapper:Callable[[Node], Type]) -> types.Fun :
		return types.Fun(tuple(unwrapper(arg.typ) for arg in self.arg_types), unwrapper(self.return_type) if self.return_type is not None else types.VOID)
@dataclass(slots=True, frozen=True)
class Mix(Node):
	name:Token
	funs:tuple[ReferTo, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"mix {self.name} {block(fun.name.operand for fun in self.funs)}"
@dataclass(slots=True, frozen=True)
class Var(Node):
	name:Token
	typ:'Node'
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"var {self.name} {self.typ}"
@dataclass(slots=True, frozen=True)
class Const(Node):
	name:Token
	value:int
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"const {self.name} {self.value}"
def block(strings:Iterable[str]) -> str:
	out = '{'
	for s in strings:
		out += '\n'+s
	return out.replace('\n','\n\t')+'\n}'
@dataclass(slots=True, frozen=True)
class Code(Node):
	statements:tuple[Node, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{block(str(i) for i in self.statements)}"
@dataclass(slots=True, frozen=True)
class If(Node):
	condition:Node
	code:Node
	else_code:Node|None
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.else_code is None:
			return f"if {self.condition} {self.code}"
		if isinstance(self.else_code, If):
			return f"if {self.condition} {self.code} el{self.else_code}"

		return f"if {self.condition} {self.code} else {self.else_code}"

@dataclass(slots=True, frozen=True)
class Return(Node):
	value:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"return {self.value}"
@dataclass(slots=True, frozen=True)
class While(Node):
	condition:Node
	code:Code
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"while {self.condition} {self.code}"
@dataclass(slots=True, frozen=True)
class Struct(Node):
	name:Token
	variables:tuple[TypedVariable, ...]
	static_variables:tuple[Assignment, ...]
	funs:tuple[Fun, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"struct {self.name} {block([str(i) for i in self.variables]+[str(i) for i in self.static_variables]+[str(i) for i in self.funs])}"
	def to_struct(self,unwrapper:Callable[[Node], Type]) -> types.Struct:
		return types.Struct(self.name.operand,tuple((arg.name.operand,unwrapper(arg.typ)) for arg in self.variables),self.uid, tuple((fun.name.operand,fun.typ(unwrapper),fun.llvmid) for fun in self.funs))
	def to_struct_kind(self,unwrapper:Callable[[Node], Type]) -> types.StructKind:
		return types.StructKind(tuple((static.var.name.operand, unwrapper(static.var.typ)) for static in self.static_variables), self.to_struct(unwrapper))
@dataclass(slots=True, frozen=True)
class Cast(Node):
	typ:'Node'
	value:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"${self.typ}({self.value})"
@dataclass(slots=True, frozen=True)
class StrCast(Node):
	length:Node
	pointer:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"$({self.length}, {self.pointer})"

@dataclass(slots=True, frozen=True)
class Str(Node):
	token:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f'"{escape(self.token.operand)}"'
@dataclass(slots=True, frozen=True)
class Int(Node):
	token:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.token.operand}"
@dataclass(slots=True, frozen=True)
class Short(Node):
	token:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.token.operand}s"
@dataclass(slots=True, frozen=True)
class CharNum(Node):
	token:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{ord(self.token.operand)}c"

@dataclass(slots=True, frozen=True)
class CharStr(Node):
	token:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"'{escape(self.token.operand)}'c"
@dataclass(slots=True, frozen=True)
class Template(Node):
	formatter:Node|None
	strings:tuple[Token, ...]
	values:tuple[Node, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		assert len(self.strings) - len(self.values) == 1, "template is corrupted"
		out = f"{self.formatter}`{escape(self.strings[0].operand)}"
		for idx, val in enumerate(self.values):
			out += f"{{{val}}}{escape(self.strings[idx+1].operand)}"
		return out + '`'

@dataclass(slots=True, frozen=True)
class TypePointer(Node):
	pointed:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"*{self.pointed}"

@dataclass(slots=True, frozen=True)
class TypeReference(Node):
	ref:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.ref}"

@dataclass(slots=True, frozen=True)
class TypeArray(Node):
	typ:Node
	size:int
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.size == 0:
			return f"[]{self.typ}"
		return f"[{self.size}]{self.typ}"

@dataclass(slots=True, frozen=True)
class TypeFun(Node):
	args:tuple[Node, ...]
	return_type:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({', '.join(f'{arg}' for arg in self.args)}) -> {self.return_type}"


@dataclass(slots=True, frozen=True)
class TypeDefinition(Node):
	name:Token
	typ:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"typedef {self.name} = {self.typ}"


@dataclass(slots=True, frozen=True)
class Enum(Node):
	name:Token
	items:tuple[Token, ...]
	typed_items:tuple[TypedVariable, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"enum {self.name} {block(f'{item}' for item in self.typed_items+self.items)}"
	def to_enum(self, unwrapper:Callable[[Node], Type]) -> types.Enum:
		return types.Enum(self.name.operand, tuple(item.operand for item in self.items), tuple((item.name.operand,unwrapper(item.typ)) for item in self.typed_items), self.uid)
	def to_enum_kind(self, unwrapper:Callable[[Node], Type]) -> types.EnumKind:
		return types.EnumKind(self.to_enum(unwrapper))


@dataclass(slots=True, frozen=True)
class Match(Node):
	value:Node
	match_as:Token
	cases:'tuple[Case, ...]'
	default:Code|None
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"match {self.value} as {self.match_as} {block(f'{case}' for case in self.cases+(f'default -> {self.default}' if self.default is not None else '',))}"
	def lookup_enum(self, enum:types.Enum, case:'Case') -> Type:
		return types.VOID

@dataclass(slots=True, frozen=True)
class Case(Node):
	name:Token
	body:Code
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name} -> {self.body}"