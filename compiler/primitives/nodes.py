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
	def __repr__(self) -> str:return str(self)
	@property
	def llvmid(self) -> str:
		return f"@.setup_module.{self.uid}"
	def module_couple_llvmid(self,uid:str) -> str:
		return f"@module.{self.uid}.{uid}"
class Node(ABC):
	place:Place
	uid:int
	def __eq__(self, __o: object) -> bool:
		if isinstance(__o, Node):
			return self.uid == __o.uid
		return NotImplemented
	def __repr__(self) -> str:return str(self)
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
		elif self.name.operand == 'Null' : return types.PTR
		elif self.name.operand == 'Argv' : return types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))) #ptr([]ptr([]char))
		elif self.name.operand == 'Argc' : return types.INT
		elif self.name.operand == 'Void' : return types.VOID
		else:
			assert False, f"Unreachable, unknown {self.name=}"
@dataclass(slots=True, frozen=True)
class BinaryOperation(Node):
	left:Node
	operation:str
	operation_place:Place
	right:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"({self.left} {self.operation} {self.right})"
	def typ(self,left:Type,right:Type, config:'Config') -> 'Type':
		op = self.operation
		assert op != ''
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
		if   op == '+'   and issamenumber: return left
		elif op == '-'   and issamenumber: return left
		elif op == '*'   and issamenumber: return left
		elif op == '//'  and issamenumber: return left
		elif op == '%'   and issamenumber: return left
		elif op == '<<'  and issamenumber: return left
		elif op == '>>'  and issamenumber: return left
		elif op == 'or'  and issamenumber: return left
		elif op == 'xor' and issamenumber: return left
		elif op == 'and' and issamenumber: return left
		elif op == '<'   and issamenumber: return types.BOOL
		elif op == '>'   and issamenumber: return types.BOOL
		elif op == '=='  and issamenumber: return types.BOOL
		elif op == '!='  and issamenumber: return types.BOOL
		elif op == '<='  and issamenumber: return types.BOOL
		elif op == '>='  and issamenumber: return types.BOOL
		elif op == 'or'  and lr == (types.BOOL, types.BOOL): return types.BOOL
		elif op == 'xor' and lr == (types.BOOL, types.BOOL): return types.BOOL
		elif op == 'and' and lr == (types.BOOL, types.BOOL): return types.BOOL
		elif op == '=='  and (isptr or is_enum): return types.BOOL
		elif op == '!='  and (isptr or is_enum): return types.BOOL
		elif op == '*'   and lr == (types.STR, types.INT): return types.STR
		elif op == '+'   and lr == (types.STR, types.STR): return types.STR
		else:
			config.errors.critical_error(ET.BIN_OP, self.operation_place, f"Unsupported binary operation '{self.operation}' for '{left}' and '{right}'")
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
		for name,fun,llvmid in struct.funs:
			if name == self.access.operand:
				return fun,llvmid
		config.errors.critical_error(ET.DOT_STRUCT, self.access.place, f"did not found field '{self.access}' of struct '{struct.name}'")
	def lookup_enum_kind(self, enum:'types.EnumKind', config:Config) -> tuple[int,types.Fun|types.Enum]:
		for idx,(name, typ) in enumerate(enum.enum.typed_items):
			if name == self.access.operand:
				return idx,types.Fun((typ,), enum.enum,types.Generics.empty())
		for idx,name in enumerate(enum.enum.items):
			if name == self.access.operand:
				return len(enum.enum.typed_items)+idx,enum.enum
		config.errors.critical_error(ET.DOT_ENUM_KIND, self.access.place, f"did not found item '{self.access}' of enum kind '{enum.name}'")
	def lookup_enum(self, enum:'types.Enum', config:Config) -> tuple[types.Fun, str]:
		for name,fun,llvmid in enum.funs:
			if name == self.access.operand:
				return fun,llvmid
		config.errors.critical_error(ET.DOT_ENUM, self.access.place, f"did not found function '{self.access}' of enum '{enum.name}'")

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
class FillGeneric(Node):
	origin:Node
	filler_types:tuple[Node, ...]
	access_place:Place
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.origin}!<{', '.join(map(str,self.filler_types))}>"
@dataclass(slots=True, frozen=True)
class Generic(Node):
	name:Token
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name}"
	def typ(self) -> types.Generic:
		return types.Generic(self.name.operand,self.uid)

generics_dict:dict[int,types.Generics] = {}
@dataclass(slots=True, frozen=True)
class Generics(Node):
	generics:tuple[Generic,...]
	implicit_generics:tuple[Generic,...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if len(self.generics) == 0:
			return f""
		return f"<{', '.join(map(str,self.generics))}>"
	def typ(self) -> types.Generics:
		out = generics_dict.get(self.uid)
		if out is None:
			out = types.Generics(tuple(i.typ() for i in self.generics),tuple(i.typ() for i in self.implicit_generics))
			generics_dict[self.uid] = out
		return out
@dataclass(slots=True, frozen=True)
class Fun(Node):
	name:Token
	arg_types:tuple[TypedVariable, ...]
	return_type:'Node|None'
	code:'Code'
	args_place:Place
	place:Place
	is_main:bool
	generics:Generics
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		prefix = f'fun {self.name}{self.generics}'
		prefix += f"({', '.join([str(i) for i in self.arg_types])})"
		if self.return_type is not None:
			prefix+=f" -> {self.return_type}"
		return f"{prefix} {self.code}"
	@property
	def llvmid(self) -> 'str':
		return f'@function.{self.name.operand}.{self.uid}'
	@property
	def return_type_place(self) -> 'Place':
		return self.return_type.place if self.return_type is not None else self.name.place
	def bound_arg_type(self,bound_arg:int,unwrapper:Callable[[Node], Type],insert_bound_args:list[Type]) -> str:
		return "{"+', '.join((*(i.llvm for i in insert_bound_args),*(unwrapper(i.typ).llvm for i in self.arg_types[:bound_arg])))+"}"
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
	generics:Generics
	variables:tuple[TypedVariable, ...]
	funs:tuple[Fun, ...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"struct {self.name}{self.generics} {block([str(i) for i in self.variables]+[str(i) for i in self.funs])}"
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
		out = '' if self.formatter is None else f"{self.formatter}"
		out += f"`{escape(self.strings[0].operand)}"
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
	filler_types:tuple[Node, ...]
	access_place:Place
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if len(self.filler_types) == 0:
			return f"{self.ref}"
		return f"{self.ref}!<{', '.join(map(str,self.filler_types))}>"

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
	generics:Generics
	typed_items:tuple[TypedVariable, ...]
	items:tuple[Token, ...]
	funs:tuple[Fun,...]
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"enum {self.name}{self.generics} {block(f'{item}' for item in self.typed_items+self.items+self.funs)}"


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
	def lookup_enum(self, enum:types.Enum, case:'Case', config:'Config') -> tuple[int,Type]:
		for idx, (name, type) in enumerate(enum.typed_items):
			if case.name.operand == name:
				return idx,type
		for idx, name in enumerate(enum.items):
			if case.name.operand == name:
				return len(enum.typed_items)+idx,types.VOID
		config.errors.critical_error(ET.MATCH_ENUM, case.name.place, f"'{enum}' can't be matched against case '{case.name}'")

@dataclass(slots=True, frozen=True)
class Case(Node):
	name:Token
	body:Code
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.name} -> {self.body}"

@dataclass(slots=True, frozen=True)
class Assert(Node):
	value:Node
	explanation:Node
	place:Place
	uid:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		return f"assert {self.value} {self.explanation}"
