#!/bin/python3.9
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, auto
import subprocess
import itertools
from sys import argv, stderr, exit
from typing import Any, Callable
@dataclass
class Config:
	self_name          : str
	file               : str
	output_file        : str
	compile_time_rules : list[tuple['Loc', str]] = field(default_factory=list)
	run_file           : bool                    = False
	silent             : bool                    = False
	run_assembler      : bool                    = True
	dump               : bool                    = False
	unsafe             : bool                    = False
def usage(config:dict[str, str]) -> str:
	return f"""Usage:
	{config.get('self_name', 'programm')} file [flags]
Notes:
	short versions of flags can be combined `-rs`
Flags:
	-h --help   : print this message
	-O --output : specify output file `-O name` (do not combine short version)
	-r          : run compiled programm 
	-s          : don't generate any debug output
	-n          : do not run assembler and linker (overrides -r)
	   --dump   : dump tokens and ast of the programm
	   --unsafe : do not type check

"""
def process_cmd_args(args:list[str]) -> Config:
	assert len(args)>0, 'Error in the function above'
	self_name = args[0]
	config:dict[str, Any] = {'self_name':self_name}
	args = args[1:]
	idx = 0
	while idx<len(args):
		arg = args[idx]
		if arg[:2] == '--':
			flag = arg[2:]
			if flag == 'help':
				print(usage(config))
				exit(0)
			elif flag == 'output':
				idx+=1
				if idx>=len(args):
					print("ERROR: expected file name after --output option", file=stderr)
					print(usage(config))
					exit(17)
				config['output_file'] = args[idx]
			elif flag == 'silent':
				config['silent'] = True
			elif flag == 'dump':
				config['dump'] = True
			elif flag == 'unsafe':
				config['unsafe'] = True
			else:
				print(f"ERROR: flag {flag} is not supported yet", file=stderr)
				print(usage(config))
				exit(1)

		elif arg[:2] =='-O':
			file = arg[2:]
			config['output_file'] = file

		elif arg[0] == '-':
			for subflag in arg[1:]:#-smth
				if subflag == 'h':
					print(usage(config))
					exit(0)
				elif subflag == 'r':
					config['run_file'] = True
				elif subflag == 's':
					config['silent'] = True
				elif subflag == 'n':
					config['run_assembler'] = False
				else:
					print(f"ERROR: flag -{subflag} is not supported yet", file=stderr)
					print(usage(config))
					exit(2)
		else:
			if config.get('file') is not None:
				print("ERROR: provided 2 files", file=stderr)
				print(usage(config))
				exit(3)
			config['file'] = arg
		idx+=1
	if config.get('file') is None:
		print("ERROR: file was not provided", file=stderr)
		print(usage(config))
		exit(4)
	if config.get('output_file') is None:
		config['output_file'] = config['file'][:config['file'].rfind('.')]
	return Config(**config)
def extract_file_text_from_config(config:Config) -> str:
	with open(config.file, encoding='utf-8') as file:
		text = file.read()
	return text+'\n'+' '*10
@dataclass
class Loc:
	file_path:str
	file_text:str
	idx:int = 0
	rows:int = 1
	cols:int = 1
	def __add__(self, number:int) -> 'Loc':
		idx, cols, rows = self.idx, self.cols, self.rows
		if idx+number>=len(self.file_text):
			print(f"ERROR: {self}: unexpected end of file", file=stderr)
			exit(5)
		for _ in range(number):
			idx+=1
			cols+=1
			if self.file_text[idx] =='\n':
				cols = 0
				rows+= 1
		return type(self)(self.file_path, self.file_text, idx, rows, cols)
	def __repr__(self) -> str:
		return f"{self.file_path}:{self.rows}:{self.cols}"
	def __lt__(self, idx:int) -> bool:
		return self.idx<idx
	@property
	def char(self) -> str:
		return self.file_text[self.idx]
	def __bool__(self) -> bool:
		return self.idx < len(self.file_text)-1
escape_to_chars = {
	'n' :'\n',
	't' :'\t',
	'v' :'\v',
	'r' :'\r',
	'\\':'\\'
}
chars_to_escape ={
	'\n':'\\n',
	'\t':'\\t',
	'\v':'\\v',
	'\r':'\\r',
	'\\':'\\\\'
}
assert len(chars_to_escape) == len(escape_to_chars)
class TT(Enum):
	DIGIT               = auto()
	WORD                = auto()
	KEYWORD             = auto()
	LEFT_CURLY_BRACKET  = auto()
	RIGHT_CURLY_BRACKET = auto()
	LEFT_PARENTHESIS    = auto()
	RIGHT_PARENTHESIS   = auto()
	STRING              = auto()
	EOF                 = auto()
	ARROW               = auto()
	SEMICOLON           = auto()
	COLON               = auto()
	COMMA               = auto()
	EQUALS_SIGN         = auto()
	PLUS                = auto()
	MINUS               = auto()
	ASTERISK            = auto()
	DOUBLE_ASTERISK     = auto()
	SLASH               = auto()
	DOUBLE_SLASH        = auto()
	PERCENT_SIGN        = auto()
	def __str__(self) -> str:
		return self.name.lower()
@dataclass
class Token:
	loc:Loc
	typ:TT
	operand: str = ''
	def __repr__(self) -> str:
		if self.typ == TT.STRING:
			return f'"{escape(self.operand)}"'
		if self.operand !='':
			return escape(self.operand)
		return escape(self.typ)
	def equals(self, typ_or_token:'TT|Token', operand:'str|None' = None) -> bool:
		if isinstance(typ_or_token, Token):
			operand = typ_or_token.operand
			typ_or_token = typ_or_token.typ
			return typ_or_token and self.operand == operand
		if operand is None:
			return self.typ == typ_or_token
		else:
			return typ_or_token and self.operand == operand

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, (TT,Token)):
			return NotImplemented
		return self.equals(other)

WHITESPACE    = " \t\n\r\v\f\b\a"
DIGITS        = "0123456789"
WORD_ALPHABET = DIGITS+"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
KEYWORDS = [
	'fun'
]
def lex(text:str, config:Config) -> list[Token]:
	loc=Loc(config.file, text, )
	programm:list[Token] = []
	while loc:
		s = loc.char
		start_loc = loc
		if s in WHITESPACE:
			loc+=1
			continue
		elif s in DIGITS:#important, that it is before word lexing
			word = s
			loc+=1
			while loc.char in DIGITS:
				word+=loc.char
				loc+=1
			programm.append(Token(start_loc, TT.DIGIT, word))
			continue
		elif s in WORD_ALPHABET:
			word = s
			loc+=1
			while loc.char in WORD_ALPHABET:
				word+=loc.char
				loc+=1

			programm.append(Token(start_loc,
			TT.KEYWORD if word in KEYWORDS else TT.WORD
			, word))
			continue
		elif s in "'\"":
			loc+=1
			word = ''
			while loc.char != s:
				if loc.char == '\\':
					loc+=1
					word+=escape_to_chars.get(loc.char, loc.char)
					loc+=1
					continue
				word+=loc.char
				loc+=1
			programm.append(Token(start_loc, TT.STRING, word))
		elif s in '}{(), ;=+%:':
			programm.append(Token(start_loc,
			{
				'{':TT.LEFT_CURLY_BRACKET,
				'}':TT.RIGHT_CURLY_BRACKET,
				'(':TT.LEFT_PARENTHESIS,
				')':TT.RIGHT_PARENTHESIS,
				';':TT.SEMICOLON,
				'=':TT.EQUALS_SIGN,
				'+':TT.PLUS,
				'%':TT.PERCENT_SIGN,
				',':TT.COMMA,
				':':TT.COLON,
			}[s]))
		elif s == '*':
			token = Token(start_loc, TT.ASTERISK)
			loc+=1
			#if loc.char == '*':
			#	loc+=1
			#	token = Token(start_loc, TT.double_asterisk)
			#TODO: come up with a way to use ** (other, than exponent)
			programm.append(token)
			continue
		elif s == '/':
			token = Token(start_loc, TT.SLASH)
			loc+=1
			if loc.char == '/':
				token = Token(start_loc, TT.DOUBLE_SLASH)
				loc+=1
			else:
				print(f"ERROR: {loc} division to the fraction is not supported yet", file=stderr)
				exit(21)
			programm.append(token)
			continue
		elif s == '-':
			token = Token(start_loc, TT.MINUS)
			loc+=1
			if loc.char == '>':
				loc+=1
				token = Token(start_loc, TT.ARROW)
			programm.append(token)
			continue
		elif s == '#':
			while loc.char != '\n':
				loc+=1
			continue
		elif s == '!':
			word = ''
			while loc.char != '\n':
				word+=loc.char
				loc+=1
			config.compile_time_rules.append((start_loc, word))
			continue
		else:
			print(f"ERROR: {loc}: Illigal char '{s}'", file=stderr)
			exit(6)
		loc+=1
	programm.append(Token(start_loc, TT.EOF))
	return programm
def join(listik:list[Any], sep:str=', ') -> str:
	return sep.join([repr(i) for i in listik])
class Node(ABC):
	pass
__id_counter = itertools.count()
get_id:Callable[[], int] = lambda:next(__id_counter)
@dataclass
class NodeTops(Node):
	tops:list[Node]
	def __repr__(self) -> str:
		sep = ', \n\n'
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"[\n\t{tab(join(self.tops, sep))}\n]"
@dataclass
class NodeFunctionCall(Node):
	name:Token
	args:'list[Node|Token]'
	def __repr__(self) -> str:
		return f"{self.name}({join(self.args)})"
@dataclass
class NodeTypedVariable(Node):
	name:Token
	typ:'Type'
	def __repr__(self) -> str:
		return f"{self.name}:{self.typ}"
@dataclass
class NodeExprStatement(Node):
	value:'Node | Token'
	def __repr__(self) -> str:
		return f"{self.value}"
@dataclass
class NodeAssignment(Node):
	var:'NodeTypedVariable'
	value:'Node|Token'
	def __repr__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass
class NodeReferTo(Node):
	name:Token
	def __repr__(self) -> str:
		return f"{self.name}"
@dataclass
class NodeBinaryExpression(Node):
	left:'Token | Node'
	operation:Token
	right:'Token | Node'
	def __repr__(self) -> str:
		return f"({self.left} {self.operation} {self.right})"
@dataclass
class NodeFun(Node):
	name:Token
	input_types:'list[NodeTypedVariable]'
	output_type:'Type'
	code:"NodeCode"
	identifier:int = field(default_factory=get_id)
	def __repr__(self) -> str:
		return f"fun {self.name} {join(self.input_types, sep=' ')} -> {self.output_type} {self.code}"
@dataclass
class NodeCode(Node):
	statements:'list[Node | Token]'
	def __repr__(self) -> str:
		new_line = '\n'
		tab = '\t'
		return f"{'{'}{new_line}{tab}{join(self.statements, f';{new_line}{tab}')}{new_line}{'}'}"
class Type(Enum):
	INT  = auto()
	STR  = auto()
	VOID = auto()
	def __int__(self) -> int:
		table:dict[Type, int] = {
			Type.VOID: 0,
			Type.INT : 1,
			Type.STR : 2,
		}
		assert len(table)==len(Type)
		return table[self]
	def __str__(self) -> str:
		return self.name.lower()
class Parser:
	def __init__(self, words:list[Token], config:Config) -> None:
		self.words = words
		self.config = config
		self.idx=0
	def adv(self) -> None:
		"""advance current word"""
		self.idx+=1
	@property
	def current(self) -> Token:
		return self.words[self.idx]
	def parse(self) -> NodeTops:
		nodes = []
		while self.current.typ != TT.EOF:
			nodes.append(self.parse_top())
		return NodeTops(nodes)
	def parse_top(self) -> Node:
		if self.current.equals(TT.KEYWORD, 'fun'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of function after keyword 'fun'", file=stderr)
				exit(8)
			name = self.current
			self.adv()

			#parse contract of the fun
			input_types:list[NodeTypedVariable] = []
			while self.next is not None:
				if self.next.typ != TT.COLON:
					break
				input_types.append(self.parse_typed_variable())

			output_type:Type = Type.VOID
			if self.current.typ == TT.ARROW: # provided any output types
				self.adv()
				output_type = self.parse_type()

			code = self.parse_code_block()
			return NodeFun(name, input_types, output_type, code)
		else:
			print(f"ERROR: {self.current.loc}: unrecognized top-level structure while parsing", file=stderr)
			exit(7)
	def parse_code_block(self) -> NodeCode:
		if self.current.typ != TT.LEFT_CURLY_BRACKET:
			print(f"ERROR: {self.current.loc}: expected code block starting with '{'{'}' ", file=stderr)
			exit(10)
		self.adv()
		code=[]
		while self.current.typ != TT.RIGHT_CURLY_BRACKET:
			code.append(self.parse_statement())
			if self.current.typ == TT.RIGHT_CURLY_BRACKET:break
			if self.current.typ != TT.SEMICOLON:
				print(f"ERROR: {self.current.loc}: expected ';' or '{'}'}' ", file=stderr)
				exit(11)
			self.adv()
		self.adv()
		return NodeCode(code)
	@property
	def next(self) -> 'Token | None':
		if len(self.words)>self.idx+1:
			return self.words[self.idx+1]
		return None
	def parse_statement(self) -> 'Node|Token':
		if self.next is not None:
			if self.next.typ == TT.COLON:
				var = self.parse_typed_variable()
				if self.current.typ != TT.EQUALS_SIGN:
					print(f"ERROR: {self.current.loc}: expected '=' after typed name", file=stderr)
					exit(19)
				self.adv()
				value = self.parse_expression()
				return NodeAssignment(var, value)
		return NodeExprStatement(self.parse_expression())
	def parse_typed_variable(self) -> NodeTypedVariable:
		name = self.current
		self.adv()#colon
		assert self.current.typ == TT.COLON, "bug in function above ^, or in this one"
		self.adv()#type
		typ = self.parse_type()

		return NodeTypedVariable(name, typ)
	def parse_type(self) -> Type:
		const = {
			'void':Type.VOID,
			'str':Type.STR,
			'int':Type.INT,
		}
		assert len(const) == len(Type)
		out = const.get(self.current.operand) # for now that is enough
		if out is None:
			print(f"ERROR: {self.current.loc}: Unrecognixed type {self.current}")
			exit(22)
		self.adv()
		return out
	def parse_expression(self) -> 'Node | Token':
		return self.parse_exp0()
	def bin_exp_parse_helper(
		self,
		nexp:'Callable[[], Node|Token]',
		operations:list[TT]
	) -> 'Node | Token':
		left = nexp()
		while self.current.typ in operations:
			op_token = self.current
			self.adv()
			right = nexp()
			left = NodeBinaryExpression(left, op_token, right)
		return left
	def parse_exp0(self) -> 'Node | Token':
		nexp = self.parse_exp1
		return self.bin_exp_parse_helper(nexp, [
			TT.PLUS,
			TT.MINUS,
		])
	def parse_exp1(self) -> 'Node | Token':
		nexp = self.parse_exp2
		return self.bin_exp_parse_helper(nexp, [
			TT.ASTERISK,
			TT.SLASH,
		])
	def parse_exp2(self) -> 'Node | Token':
		nexp = self.parse_term
		return self.bin_exp_parse_helper(nexp, [
			TT.DOUBLE_ASTERISK,
			TT.DOUBLE_SLASH,
			TT.PERCENT_SIGN,
		])
	def parse_term(self) -> 'Node | Token':
		if self.current.typ in (TT.DIGIT, TT.STRING):
			token = self.current
			self.adv()
			return token
		if self.current.typ == TT.LEFT_PARENTHESIS:
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:
				print(f"ERROR: {self.current.loc}: expected ')'", file=stderr)
				exit(12)
			self.adv()
			return expr
		if self.current.typ == TT.WORD: #trying to extract function call
			name = self.current
			self.adv()
			if self.current.typ == TT.LEFT_PARENTHESIS:
				self.adv()
				args = []
				while self.current.typ != TT.RIGHT_PARENTHESIS:
					args.append(self.parse_expression())
					if self.current.typ == TT.RIGHT_PARENTHESIS:break
					if self.current.typ != TT.COMMA:
						print(f"ERROR: {self.current.loc}: expected ', ' or ')' ", file=stderr)
						exit(13)
					self.adv()
				self.adv()
				return NodeFunctionCall(name, args)
			return NodeReferTo(name)
		else:
			print(f"ERROR: {self.current.loc}: Unexpexted token while parsing term", file=stderr)
			exit(18)
INTRINSICS = {
	'print':(
"""
	pop rsi;print syscall
	pop rdx
	mov rdi, 1
	mov rax, 1
	syscall
""", (Type.STR, ), Type.VOID, get_id()),

}
def find_fun_by_name(ast:NodeTops, name:Token) -> NodeFun:
	for top in ast.tops:
		if isinstance(top, NodeFun):
			if top.name == name:
				return top

	print(f"ERROR: {name.loc}: did not find function '{name}'", file=stderr)
	exit(23)
class GenerateAssembly:
	def __init__(self, ast:NodeTops, config:Config) -> None:
		self.strings_to_push   : list[Token]             = []
		self.intrinsics_to_add : set[str]                = set()
		self.data_stack        : list[Type]              = []
		self.variables         : list[NodeTypedVariable] = []
		self.config            : Config                  = config
		self.ast               : NodeTops                = ast
		self.generate_assembly()
	def visit_fun(self, node:NodeFun) -> None:

		self.file.write(f"""
fun_{node.identifier}:;{node.name.operand}
	mov [ret_stack_rsp], rsp ; starting fun
	mov rsp, rax ; swapping back ret_stack and data_stack 
""")

		self.file.write(f"""
	mov rax, [ret_stack_rsp] ; assign vars for fun""")
		for var in reversed(node.input_types):
			self.variables.append(var)
			self.file.write(f"""
	sub rax, {8*int(var.typ)} ; var '{var.name}' at {var.name.loc}""")
			for idx in range(int(var.typ)-1, -1, -1):
				self.file.write(f"""
	pop rbx
	mov [rax+{8*idx}], rbx""")
			self.file.write('\n')

		self.file.write("""
	mov [ret_stack_rsp], rax""")


		self.visit(node.code)
		self.file.write(f"""
	mov rax, rsp; swapping ret_stack and data_stack 
	mov rsp, [ret_stack_rsp] ; ending fun""")
		for var in self.variables:
			self.file.write(f"""
	add rsp, {8*int(var.typ)}; remove variable '{var.name}' at {var.name.loc}""")
		self.variables = []
		self.file.write('\n\tret')
	def visit_code(self, node:NodeCode) -> None:
		for statemnet in node.statements:
			self.visit(statemnet)
	def visit_function_call(self, node:NodeFunctionCall) -> None:
		for arg in node.args:
			self.visit(arg)
		intrinsic = INTRINSICS.get(node.name.operand)
		if intrinsic is not None:
			self.intrinsics_to_add.add(node.name.operand)
			for _ in intrinsic[1]:
				self.data_stack.pop()
			self.data_stack.append(intrinsic[2])
			identifier = f"intrinsic_{intrinsic[3]}"
		else:
			top = find_fun_by_name(self.ast,node.name)
			for _ in top.input_types:
				self.data_stack.pop()
			self.data_stack.append(top.output_type)
			identifier = f"fun_{top.identifier}"
		self.file.write(f"""
	mov rax, rsp ; call function 
	mov rsp, [ret_stack_rsp] ; {node.name.loc}
	call {identifier};{node.name.operand}
	mov [ret_stack_rsp], rsp
	mov rsp, rax
""")
	def visit_token(self, token:Token) -> None:
		if token.typ == TT.DIGIT:
			self.file.write(f"""
    push {token.operand} ; push number {token.loc}
""")
			self.data_stack.append(Type.INT)
		elif token.typ == TT.STRING:
			self.file.write(f"""
	push {len(token.operand)} ; push string {token.loc}
	push str_{len(self.strings_to_push)}
""")
			self.strings_to_push.append(token)
			self.data_stack.append(Type.STR)
		else:
			assert False, f"Unreachable: {token.typ=}"
	def visit_bin_exp(self, node:NodeBinaryExpression) -> None:
		self.visit(node.left)
		self.visit(node.right)
		if node.operation == TT.PERCENT_SIGN:
			self.file.write(f"""
	pop rbx; operating {node.operation} at {node.operation.loc}
	pop rax
	div rbx
	push rdx
""")
			return
		operations:dict[TT, str] = {
		TT.PLUS:'add rax, rbx',
		TT.MINUS:'sub rax, rbx',
		TT.ASTERISK:'mul rbx',
		TT.DOUBLE_SLASH:'div rbx',
		}
		operation = operations.get(node.operation.typ)
		if operation is None:
			print(f"ERROR: {node.operation.loc}: op {node.operation} is not implemented yet", file=stderr)
			exit(20)
		self.file.write(f"""
	pop rbx; operating {node.operation} at {node.operation.loc}
	pop rax
	{operation}
	push rax
""")
		self.data_stack.pop()#type_check, I count on you
		self.data_stack.pop()
		self.data_stack.append(Type.INT)
	def visit_expr_state(self, node:NodeExprStatement) -> None:
		self.visit(node.value)
		self.file.write(f"""
	sub rsp, {8*int(self.data_stack.pop())} ;pop expr result
""")
		self.file.write('\n\n')
	def visit_assignment(self, node:NodeAssignment) -> None:
		self.visit(node.value) # get a value to store
		typ = self.data_stack.pop()
		self.variables.append(node.var)
		self.file.write(f"""
	mov rax, [ret_stack_rsp] ; assign '{node.var.name}'
	sub rax, {8*int(typ)} ; at {node.var.name.loc}
	mov [ret_stack_rsp], rax""")
		for idx in range(int(typ)-1, -1, -1):
			self.file.write(f"""
	pop rbx
	mov [rax+{8*idx}], rbx""")
		self.file.write('\n')
	def visit_referer(self, node:NodeReferTo) -> None:
		idx = len(self.variables)-1
		offset = 0
		while idx>=0:
			var = self.variables[idx]
			if var.name == node.name:
				typ = var.typ
				break
			offset+=int(var.typ)
			idx-=1
		else:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}'", file=stderr)
			exit(9)
		self.file.write(f'''
	mov rax, [ret_stack_rsp]; refrence '{node.name}' at {node.name.loc}''')
		for i in range(int(typ)):
			self.file.write(f'''
	push QWORD [rax+{(offset+i)*8}]''')
		self.file.write('\n')
		self.data_stack.append(typ)
	def visit(self, node:'Node|Token') -> None:
		if   type(node) == NodeFun             : self.visit_fun          (node)
		elif type(node) == NodeCode            : self.visit_code         (node)
		elif type(node) == NodeFunctionCall    : self.visit_function_call(node)
		elif type(node) == NodeBinaryExpression: self.visit_bin_exp      (node)
		elif type(node) == NodeExprStatement   : self.visit_expr_state   (node)
		elif type(node) == Token               : self.visit_token        (node)
		elif type(node) == NodeAssignment      : self.visit_assignment   (node)
		elif type(node) == NodeReferTo         : self.visit_referer      (node)
		else:
			assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		with open(self.config.output_file + '.asm', 'wt',encoding='UTF-8') as file:
			self.file = file
			file.write('segment .text')
			for top in self.ast.tops:
				self.visit(top)
			for intrinsic in self.intrinsics_to_add:
				file.write(f"""
intrinsic_{INTRINSICS[intrinsic][3]}: ;{intrinsic}
	mov [ret_stack_rsp], rsp
	mov rsp, rax;default
{INTRINSICS[intrinsic][0]}
	mov rax, rsp;default
	mov rsp, [ret_stack_rsp]
	ret
""")
			for top in self.ast.tops:
				if isinstance(top, NodeFun):
					if top.name.operand == 'main':
						break
			else:
				print(f"ERROR: did not find entry point (function 'main')", file=stderr)
				exit(24)
			file.write(f"""
global _start
_start:
	mov [args_ptr], rsp
	mov rax, ret_stack_end
	mov [ret_stack_rsp], rax ; default stuff
	call fun_{top.identifier} ; call main fun
	mov rax, 60
	mov rdi, 0
	syscall
segment .bss
	args_ptr: resq 1
	ret_stack_rsp: resq 1
	ret_stack: resb 65536
	ret_stack_end:
	;mem: resb 15384752
segment .data
""")
			for idx, string in enumerate(self.strings_to_push):
				file.write(f"""
str_{idx}: db {', '.join([str(ord(i)) for i in string.operand])} ; {string.loc}
""")
def run_command(command:list[str], config:Config) -> int:
	if not config.silent:
		print(f"[CMD] {' '.join(command)}" )
	return subprocess.call(command)
def run_assembler(config:Config) -> None:
	if not config.run_assembler:
		return
	run:Callable[[list[str]], int] = lambda x:run_command(x, config)
	ret_code = run(['nasm', config.output_file+'.asm', '-f', 'elf64', '-g'])
	if ret_code != 0:
		print(f"ERROR: nasm exited abnormaly with exit code {ret_code}", file=stderr)
		exit(14)
	ret_code = run(['ld', '-o', config.output_file+'.out', config.output_file+'.o'])
	if ret_code != 0:
		print(f"ERROR: GNU linker exited abnormaly with exit code {ret_code}", file=stderr)
		exit(15)
	ret_code = run(['chmod', '+x', config.output_file+'.out'])
	if ret_code != 0:
		print(f"ERROR: chmod exited abnormaly with exit code {ret_code}", file=stderr)
		exit(16)

class TypeCheck:
	def __init__(self, ast:NodeTops, config:Config) -> None:
		if config.unsafe:
			return
		self.ast = ast
		self.config = config
		self.variables:list[NodeTypedVariable] = []
		for top in ast.tops:
			self.check(top)

	

	def check_fun(self, node:NodeFun) -> Type:
		self.variables = node.input_types
		ret_typ = self.check(node.code)
		if node.output_type != ret_typ:
			print(f"ERROR: {node.name.loc}: specifyed return type ({node.output_type}) does not match actual return type ({ret_typ})",file=stderr)
			exit(26)
		self.variables = []
	def check_code(self, node:NodeCode) -> Type:
		for statement in node.statements:
			#@return
			self.check(statement)
		return Type.VOID
	def check_function_call(self, node:NodeFunctionCall) -> Type:
		intrinsic = INTRINSICS.get(node.name.operand)
		if intrinsic is not None:
			_,input_types,output_type,_ = intrinsic
		else:
			nodee = find_fun_by_name(self.ast,node.name)
			input_types,output_type = [t.typ for t in nodee.input_types],nodee.output_type
		if len(input_types) != len(node.args):
			print(f"ERROR: {node.name.loc}: function {node.name} accepts {len(input_types)} argumets, provided {len(node.args)}",file=stderr)
			exit(27)
		for idx,arg in enumerate(node.args):
			typ = self.check(arg)
			needed = input_types[idx]
			if typ != needed:
				print(f"ERROR: {node.name.loc}: argument {idx} has incompatable type {typ}, expected {needed}",file=stderr)
				exit(28)
		return output_type
	
	def check_bin_exp(self, node:NodeBinaryExpression) -> Type:
		def bin(left_type:Type, right_type:Type, ret_type:Type, name:str) -> Type:
			l = self.check(node.left)
			r = self.check(node.right)
			if left_type == l and right_type == r:
				return ret_type
			print(f"ERROR: {node.operation.loc}: unsupported operation '{name}' for {r} and {l}",file=stderr)
			exit(25)
		if   node.operation == TT.PLUS         : return bin(Type.INT, Type.INT, Type.INT, '+' )
		elif node.operation == TT.MINUS        : return bin(Type.INT, Type.INT, Type.INT, '-' )
		elif node.operation == TT.ASTERISK     : return bin(Type.INT, Type.INT, Type.INT, '*' )
		elif node.operation == TT.DOUBLE_SLASH : return bin(Type.INT, Type.INT, Type.INT, '//')
		elif node.operation == TT.PERCENT_SIGN : return bin(Type.INT, Type.INT, Type.INT, '%' )
		else:
			assert False, "Unreachable {node.operation=}"
	def check_expr_state(self, node:NodeExprStatement) -> Type:
		self.check(node.value)
		return Type.VOID
	def check_token(self, token:Token) -> Type:
		if   token == TT.STRING : return Type.STR
		elif token == TT.DIGIT  : return Type.INT
		else:
			assert False, f"unreachable {token.typ=}"
	def check_assignment(self, node:NodeAssignment) -> Type:
		assert False, "'check_assignment' is not implemented yet"
	
	def check_referer(self, node:NodeReferTo) -> Type:
		assert False, "'check_referer' is not implemented yet"
	
	def check(self, node:'Node|Token') -> Type:
		if   type(node) == NodeFun              : return self.check_fun           (node)
		elif type(node) == NodeCode             : return self.check_code          (node)
		elif type(node) == NodeFunctionCall     : return self.check_function_call (node)
		elif type(node) == NodeBinaryExpression : return self.check_bin_exp       (node)
		elif type(node) == NodeExprStatement    : return self.check_expr_state    (node)
		elif type(node) == Token                : return self.check_token         (node)
		elif type(node) == NodeAssignment       : return self.check_assignment    (node)
		elif type(node) == NodeReferTo          : return self.check_referer       (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"

		
def escape(string:Any) -> str:
	string = f"{string}"
	out = ''
	for char in string:
		out+=chars_to_escape.get(char, char)
	return out
def dump_tokens(tokens:list[Token], config:Config) -> None:
	print("Tokens:" )
	for token in tokens:
		print(f"\t{token.loc}: \t{token}" )
def dump_ast(ast:NodeTops, config:Config) -> None:
	print("Ast:" )
	print(ast)
def main() -> None:
	config = process_cmd_args(argv)#["me","foo.lang"])
	text = extract_file_text_from_config(config)
	tokens = lex(text, config)

	if config.dump:
		dump_tokens(tokens, config)

	ast = Parser(tokens, config).parse()

	if config.dump:
		dump_ast(ast, config)
		exit(0)

	TypeCheck(ast,config)
	GenerateAssembly(ast, config)

	run_assembler(config)

	if config.run_file and config.run_assembler:
		ret_code = run_command([f"./{config.output_file}.out"], config)
		exit(ret_code)
if __name__ == '__main__':
	main()