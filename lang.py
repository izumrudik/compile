#!/bin/python3.10
#pylint:disable=C0114,C0115,C0116,C0123,C0301,C0302,C0321,
#pylint:disable=R0903, R0902, R1705
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, auto
import subprocess
import itertools
import sys
from sys import argv, stderr
from typing import Any, Callable
__id_counter = itertools.count()
get_id:Callable[[], int] = lambda:next(__id_counter)
@dataclass(frozen=True)
class Config:
	self_name          : str
	file               : str
	output_file        : str
	run_file           : bool                    = False
	silent             : bool                    = False
	run_assembler      : bool                    = True
	dump               : bool                    = False
def usage(config:'dict[str, str]') -> str:
	return f"""Usage:
	{config.get('self_name', 'program')} file [flags]
Notes:
	short versions of flags can be combined for example `-r -s` can be shorten to `-rs`
Flags:
	-h --help   : print this message
	-O --output : specify output file `-O name` (do not combine short version)
	-r          : run compiled program 
	-s          : don't generate any debug output
	-n          : do not run assembler and linker (overrides -r)
	   --dump   : dump tokens and ast of the program

"""
def process_cmd_args(args:'list[str]') -> Config:
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
				sys.exit(0)
			elif flag == 'output':
				idx+=1
				if idx>=len(args):
					print("ERROR: expected file name after --output option", file=stderr)
					print(usage(config))
					sys.exit(1)
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
				sys.exit(2)

		elif arg[:2] =='-O':
			file = arg[2:]
			config['output_file'] = file

		elif arg[0] == '-':
			for subflag in arg[1:]:
				if subflag == 'h':
					print(usage(config))
					sys.exit(0)
				elif subflag == 'r':
					config['run_file'] = True
				elif subflag == 's':
					config['silent'] = True
				elif subflag == 'n':
					config['run_assembler'] = False
				else:
					print(f"ERROR: flag -{subflag} is not supported yet", file=stderr)
					print(usage(config))
					sys.exit(3)
		else:
			if config.get('file') is not None:
				print("ERROR: provided 2 files", file=stderr)
				print(usage(config))
				sys.exit(4)
			config['file'] = arg
		idx+=1
	if config.get('file') is None:
		print("ERROR: file was not provided", file=stderr)
		print(usage(config))
		sys.exit(5)
	if config.get('output_file') is None:
		config['output_file'] = config['file'][:config['file'].rfind('.')]
	return Config(**config)
def extract_file_text_from_config(config:Config) -> str:
	with open(config.file, encoding='utf-8') as file:
		text = file.read()
	return text+'\n'+' '*10
@dataclass(frozen=True, order=True)
class Loc:
	file_path:str
	file_text:str = field(compare=False,repr=False)
	idx:int    = 0
	__rows:int = field(default=1,compare=False,repr=False)
	__cols:int = field(default=1,compare=False,repr=False)
	def __add__(self, number:int) -> 'Loc':
		idx, cols, rows = self.idx, self.__cols, self.__rows
		if idx+number>=len(self.file_text):
			print(f"ERROR: {self}: unexpected end of file", file=stderr)
			sys.exit(6)
		for _ in range(number):
			idx+=1
			cols+=1
			if self.file_text[idx] =='\n':
				cols = 0
				rows+= 1
		return self.__class__(self.file_path, self.file_text, idx, rows, cols)
	def __str__(self) -> str:
		return f"{self.file_path}:{self.__rows}:{self.__cols}"

	@property
	def char(self) -> str:
		return self.file_text[self.idx]
	def __bool__(self) -> bool:
		return self.idx < len(self.file_text)-1
class TT(Enum):
	DIGIT                 = auto()
	WORD                  = auto()
	KEYWORD               = auto()
	LEFT_CURLY_BRACKET    = auto()
	RIGHT_CURLY_BRACKET   = auto()
	LEFT_PARENTHESIS      = auto()
	RIGHT_PARENTHESIS     = auto()
	STRING                = auto()
	EOF                   = auto()
	ARROW                 = auto()
	SEMICOLON             = auto()
	NEWLINE               = auto()
	COLON                 = auto()
	COMMA                 = auto()
	EQUALS_SIGN           = auto()
	NOT                   = auto()
	NOT_EQUALS_SIGN       = auto()
	DOUBLE_EQUALS_SIGN    = auto()
	GREATER_SIGN          = auto()
	GREATER_OR_EQUAL_SIGN = auto()
	LESS_SIGN             = auto()
	LESS_OR_EQUAL_SIGN    = auto()
	PLUS                  = auto()
	MINUS                 = auto()
	ASTERISK              = auto()
	DOUBLE_ASTERISK       = auto()
	SLASH                 = auto()
	DOUBLE_SLASH          = auto()
	PERCENT_SIGN          = auto()
	def __str__(self) -> str:
		names = {
			TT.GREATER_SIGN:'>',
			TT.LESS_SIGN:'<',
			TT.LESS_OR_EQUAL_SIGN:'<=',
			TT.GREATER_OR_EQUAL_SIGN:'>=',
			TT.DOUBLE_EQUALS_SIGN:'==',
			TT.NOT:'!',
			TT.NOT_EQUALS_SIGN:'!=',
			TT.PLUS:'+',
			TT.MINUS:'-',
			TT.ASTERISK:'*',
			TT.DOUBLE_ASTERISK:'**',
			TT.SLASH:'/',
			TT.DOUBLE_SLASH:'//',
			TT.PERCENT_SIGN:'%',
			TT.NEWLINE:'\n',
		}
		return names.get(self,self.name.lower())
@dataclass(frozen=True, eq=False)
class Token:
	loc:Loc = field(compare=False)
	typ:TT
	operand: str = ''
	identifier: int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		if self.typ == TT.STRING:
			return f'"{escape(self.operand)}"'
		if self.operand !='':
			return escape(self.operand)
		return escape(self.typ)
	def equals(self, typ_or_token:'TT|Token', operand:'str|None' = None) -> bool:
		if isinstance(typ_or_token, Token):
			operand = typ_or_token.operand
			typ_or_token = typ_or_token.typ
			return self.typ == typ_or_token and self.operand == operand
		if operand is None:
			return self.typ == typ_or_token
		return self.typ == typ_or_token and self.operand == operand

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, (TT,Token)):
			return NotImplemented
		return self.equals(other)

	def __hash__(self) -> int:
		return hash((self.typ, self.operand))
escape_to_chars = {
	't' :'\t',
	'n' :'\n',
	'r' :'\r',
	'v' :'\v',
	'f':'\f',
	'b':'\b',
	'a':'\a',
	"'":"'",
	'"':'"',
	'\\':'\\'
}
chars_to_escape ={
	'\t':'\\t',
	'\n':'\\n',
	'\r':'\\r',
	'\v':'\\v',
	'\f':'\\f',
	'\b':'\\b',
	'\a':'\\a',
	'\'':"\\'",
	'\"':'\\"',
	'\\':'\\\\'
}
assert len(chars_to_escape) == len(escape_to_chars)
WHITESPACE    = " \t\n\r\v\f\b\a"
DIGITS        = "0123456789"
WORD_ALPHABET = DIGITS+"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
KEYWORDS = [
	'fun',
	'memo',
	'if',
	'True',
	'False',
	'or',
	'xor',
	'and',
	'else',
	'elif',
]
def lex(text:str, config:Config) -> 'list[Token]':
	loc=Loc(config.file, text,)
	start_loc = loc
	program: list[Token] = []
	while loc:
		char = loc.char
		start_loc = loc
		if char in '}{(),;+%:':
			program.append(Token(start_loc,
			{
				'{':TT.LEFT_CURLY_BRACKET,
				'}':TT.RIGHT_CURLY_BRACKET,
				'(':TT.LEFT_PARENTHESIS,
				')':TT.RIGHT_PARENTHESIS,
				';':TT.SEMICOLON,
				'+':TT.PLUS,
				'%':TT.PERCENT_SIGN,
				',':TT.COMMA,
				':':TT.COLON,
			}[char]))
		elif char == '\\':#escape any char with one-char comment
			loc+=2
			continue
		elif char in WHITESPACE:
			if char == '\n':#semicolon replacement
				program.append(Token(start_loc,TT.NEWLINE))
			loc+=1
			continue
		elif char in DIGITS:# important, that it is before word lexing
			word = char
			loc += 1
			while loc.char in DIGITS:
				word+=loc.char
				loc+=1
			program.append(Token(start_loc, TT.DIGIT, word))
			continue
		elif char in WORD_ALPHABET:
			word = char
			loc+=1
			while loc.char in WORD_ALPHABET:
				word+=loc.char
				loc+=1

			program.append(Token(start_loc,
			TT.KEYWORD if word in KEYWORDS else TT.WORD
			, word))
			continue
		elif char in "'\"":
			loc+=1
			word = ''
			while loc.char != char:
				if loc.char == '\\':
					loc+=1
					word+=escape_to_chars.get(loc.char, loc.char)
					loc+=1
					continue
				word+=loc.char
				loc+=1
			program.append(Token(start_loc, TT.STRING, word))
		elif char == '*':
			token = Token(start_loc, TT.ASTERISK)
			loc+=1
			#if loc.char == '*':
			#	loc+=1
			#	token = Token(start_loc, TT.double_asterisk)
			program.append(token)
			continue
		elif char == '/':
			token = Token(start_loc, TT.SLASH)
			loc+=1
			if loc.char == '/':
				token = Token(start_loc, TT.DOUBLE_SLASH)
				loc+=1
			else:
				print(f"ERROR: {loc} division to the fraction is not supported yet", file=stderr)
				sys.exit(7)
			program.append(token)
			continue
		elif char == '=':
			token = Token(start_loc, TT.EQUALS_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.DOUBLE_EQUALS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '!':
			token = Token(start_loc, TT.NOT)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.NOT_EQUALS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '>':
			token = Token(start_loc, TT.GREATER_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.GREATER_OR_EQUAL_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '<':
			token = Token(start_loc, TT.LESS_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.LESS_OR_EQUAL_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '-':
			token = Token(start_loc, TT.MINUS)
			loc+=1
			if loc.char == '>':
				loc+=1
				token = Token(start_loc, TT.ARROW)
			program.append(token)
			continue
		elif char == '#':
			while loc.char != '\n':
				loc+=1
			continue
		else:
			print(f"ERROR: {loc}: Illegal char '{char}'", file=stderr)
			sys.exit(8)
		loc+=1
	program.append(Token(start_loc, TT.EOF))
	return program
def join(some_list:'list[Any]', sep:str=', ') -> str:
	return sep.join([str(i) for i in some_list])
class Node(ABC):
	pass
@dataclass(frozen=True)
class NodeTops(Node):
	tops:'list[Node]'
	def __str__(self) -> str:
		sep = '\n'
		return f"{join(self.tops, sep)}"
@dataclass(frozen=True)
class NodeFunctionCall(Node):
	name:Token
	args:'list[Node|Token]'
	def __str__(self) -> str:
		return f"{self.name}({join(self.args)})"
@dataclass(frozen=True)
class NodeTypedVariable(Node):
	name:Token
	typ:'Type'
	def __str__(self) -> str:
		return f"{self.name}: {self.typ}"
@dataclass(frozen=True)
class NodeExprStatement(Node):
	value:'Node | Token'
	def __str__(self) -> str:
		return f"{self.value}"
@dataclass(frozen=True)
class NodeAssignment(Node):
	var:'NodeTypedVariable'
	value:'Node|Token'
	def __str__(self) -> str:
		return f"{self.var} = {self.value}"
@dataclass(frozen=True)
class NodeReAssignment(Node):
	name:'Token'
	value:'Node|Token'
	def __str__(self) -> str:
		return f"{self.name} = {self.value}"
@dataclass(frozen=True)
class NodeDefining(Node):
	var:'NodeTypedVariable'
	def __str__(self) -> str:
		return f"{self.var}"
@dataclass(frozen=True)
class NodeReferTo(Node):
	name:Token
	def __str__(self) -> str:
		return f"{self.name}"
@dataclass(frozen=True)
class NodeIntrinsicConstant(Node):
	name:Token
	def __str__(self) -> str:
		return f"{self.name}"
	@property
	def typ(self) -> 'Type':
		if   self.name.operand == 'False': return Type.BOOL
		elif self.name.operand == 'True' : return Type.BOOL
		else:
			assert False, f"Unreachable, unknown {self.name=}"
@dataclass(frozen=True)
class NodeBinaryExpression(Node):
	left:'Token | Node'
	operation:Token
	right:'Token | Node'
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
class NodeUnaryExpression(Node):
	operation:Token
	right:'Token | Node'
	def __str__(self) -> str:
		return f"({self.operation} {self.right})"
	@property
	def typ(self) -> 'Type':
		if self.operation == TT.NOT: return Type.BOOL
		else:
			assert False, f"Unreachable, {self.operation=}"
@dataclass(frozen=True)
class NodeFun(Node):
	name:Token
	arg_types:'list[NodeTypedVariable]'
	output_type:'Type'
	code:"NodeCode"
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		if len(self.arg_types) > 0:
			return f"fun {self.name} {join(self.arg_types, sep=' ')} -> {self.output_type} {self.code}"
		return f"fun {self.name} -> {self.output_type} {self.code}"
@dataclass(frozen=True)
class NodeMemo(Node):
	name:'Token'
	size:int
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		return f"memo {self.name} {self.size}"
@dataclass(frozen=True)
class NodeCode(Node):
	statements:'list[Node | Token]'
	def __str__(self) -> str:
		new_line = '\n'
		tab:Callable[[str], str] = lambda s: s.replace('\n', '\n\t')
		return f"{{{tab(new_line+join(self.statements, f'{new_line}'))}{new_line}}}"
@dataclass(frozen=True)
class NodeIf(Node):
	loc:'Loc'
	condition:'Node|Token'
	code:'Node'
	else_code:'Node|None' = None
	identifier:int = field(default_factory=get_id,compare=False,repr=False)
	def __str__(self) -> str:
		if self.else_code is None:
			return f"if {self.condition} {self.code}"
		if isinstance(self.else_code,NodeIf):
			return f"if {self.condition} {self.code} el{self.else_code}"

		return f"if {self.condition} {self.code} else {self.else_code}"	
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
class Parser:
	__slots__ = ('words','config','idx')
	def __init__(self, words:'list[Token]', config:Config) -> None:
		self.words = words
		self.config = config
		self.idx=0
	def adv(self) -> None:
		"""advance current word"""
		self.idx+=1
		while self.current == TT.NEWLINE:
			self.idx+=1
	@property
	def current(self) -> Token:
		return self.words[self.idx]
	def parse(self) -> NodeTops:
		nodes = []
		while self.current == TT.NEWLINE:
			self.adv() # skip newlines
		while self.current.typ != TT.EOF:
			top = self.parse_top()
			nodes.append(top)
			while self.current == TT.NEWLINE:
				self.adv() # skip newlines
		return NodeTops(nodes)
	def parse_top(self) -> Node:
		if self.current.equals(TT.KEYWORD, 'fun'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of function after keyword 'fun'", file=stderr)
				sys.exit(9)
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
		elif self.current.equals(TT.KEYWORD, 'memo'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of memory region after keyword 'memo'", file=stderr)
				sys.exit(10)
			name = self.current
			self.adv()
			size = self.parse_CTE()
			return NodeMemo(name,size)
		else:
			print(f"ERROR: {self.current.loc}: unrecognized top-level structure while parsing", file=stderr)
			sys.exit(11)
	def parse_CTE(self) -> int:
		if self.current != TT.DIGIT:
			print(f"ERROR: {self.current.loc}: compile-time-evaluation supports only digits now",file=stderr)
			sys.exit(12)
		digit = self.current
		self.adv()
		return int(digit.operand)
	def parse_code_block(self) -> NodeCode:
		if self.current.typ != TT.LEFT_CURLY_BRACKET:
			print(f"ERROR: {self.current.loc}: expected code block starting with '{{' ", file=stderr)
			sys.exit(13)
		self.adv()
		code=[]
		while self.current == TT.SEMICOLON:
			self.adv()
		while self.current != TT.RIGHT_CURLY_BRACKET:
			statement = self.parse_statement()
			code.append(statement)
			if self.current == TT.RIGHT_CURLY_BRACKET:
				break
			if self.words[self.idx-1] != TT.NEWLINE:#there was at least 1 self.adv(), so we safe (for '{')
				if self.current != TT.SEMICOLON:
					print(f"ERROR: {self.current.loc}: expected newline, ';' or '}}' ", file=stderr)
					sys.exit(14)
			while self.current == TT.SEMICOLON:
				self.adv()
		self.adv()
		return NodeCode(code)

	@property
	def next(self) -> 'Token | None':
		if len(self.words)>self.idx+1:
			return self.words[self.idx+1]
		return None
	def parse_statement(self) -> 'Node|Token':
		if self.next is not None:#variables
			if self.next == TT.COLON:
				var = self.parse_typed_variable()
				if self.current.typ != TT.EQUALS_SIGN:#var:type
					return NodeDefining(var)
				#var:type = value
				self.adv()
				value = self.parse_expression()
				return NodeAssignment(var, value)
			elif self.next == TT.EQUALS_SIGN:#var = value
				name = self.current
				self.adv()#equals sign
				self.adv()#actual expr
				value = self.parse_expression()
				return NodeReAssignment(name,value)
		if self.current.equals(TT.KEYWORD,'if'):
			return self.parse_if()
		return NodeExprStatement(self.parse_expression())
	def parse_if(self) -> Node:
		loc = self.current.loc
		self.adv()#skip keyword
		condition = self.parse_expression()
		if_code = self.parse_code_block()
		if self.current.equals(TT.KEYWORD, 'elif'):
			else_block = self.parse_if()
			return NodeIf(loc,condition,if_code,else_block)
		if self.current.equals(TT.KEYWORD, 'else'):
			self.adv()
			else_code = self.parse_code_block()
			return NodeIf(loc,condition,if_code,else_code)
		return NodeIf(loc,condition,if_code)

	def parse_typed_variable(self) -> NodeTypedVariable:
		name = self.current
		self.adv()#colon
		assert self.current.typ == TT.COLON, "bug in function above ^, or in this one"
		self.adv()#type
		typ = self.parse_type()

		return NodeTypedVariable(name, typ)
	def parse_type(self) -> Type:
		const = {
			'void': Type.VOID,
			'str' : Type.STR,
			'int' : Type.INT,
			'bool': Type.BOOL,
			'ptr' : Type.PTR,
		}
		assert len(const) == len(Type)
		out = const.get(self.current.operand) # for now that is enough
		if out is None:
			print(f"ERROR: {self.current.loc}: Unrecognized type {self.current}",file=stderr)
			sys.exit(15)
		self.adv()
		return out
	def parse_expression(self) -> 'Node | Token':
		return self.parse_exp0()
	def bin_exp_parse_helper(
		self,
		next_exp:'Callable[[], Node|Token]',
		operations:'tuple[TT, ...]'
	) -> 'Node | Token':
		left = next_exp()
		while self.current.typ in operations:
			op_token = self.current
			self.adv()
			right = next_exp()
			left = NodeBinaryExpression(left, op_token, right)
		return left

	def parse_exp0(self) -> 'Node | Token':
		self_exp = self.parse_exp0
		next_exp = self.parse_exp1
		operations = (
			TT.NOT,
		)
		if self.current.typ in operations:
			op_token = self.current
			self.adv()
			right = self_exp()
			return NodeUnaryExpression(op_token, right)
		return next_exp()

	def parse_exp1(self) -> 'Node | Token':
		next_exp = self.parse_exp2
		return self.bin_exp_parse_helper(next_exp,(
			TT.LESS_SIGN,
			TT.GREATER_SIGN,
			TT.DOUBLE_EQUALS_SIGN,
			TT.NOT_EQUALS_SIGN,
			TT.LESS_OR_EQUAL_SIGN,
			TT.GREATER_OR_EQUAL_SIGN,
		))

	def parse_exp2(self) -> 'Node | Token':
		next_exp = self.parse_exp3
		return self.bin_exp_parse_helper(next_exp, (
			TT.PLUS,
			TT.MINUS,
		))
	def parse_exp3(self) -> 'Node | Token':
		next_exp = self.parse_exp4
		return self.bin_exp_parse_helper(next_exp, (
			TT.ASTERISK,
			TT.SLASH,
		))
	def parse_exp4(self) -> 'Node | Token':
		next_exp = self.parse_exp5
		return self.bin_exp_parse_helper(next_exp, (
			TT.DOUBLE_ASTERISK,
			TT.DOUBLE_SLASH,
			TT.PERCENT_SIGN,
		))
	def parse_exp5(self) -> 'Node | Token':
		next_exp = self.parse_term
		operations = [
			'or',
			'xor',
			'and',
		]
		left = next_exp()
		while self.current == TT.KEYWORD and self.current.operand in operations:
			op_token = self.current
			self.adv()
			right = next_exp()
			left = NodeBinaryExpression(left, op_token, right)
		return left

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
				sys.exit(16)
			self.adv()
			return expr
		if self.current == TT.WORD: #trying to extract function call
			name = self.current
			self.adv()
			if self.current.typ == TT.LEFT_PARENTHESIS:
				self.adv()
				args = []
				while self.current.typ != TT.RIGHT_PARENTHESIS:
					args.append(self.parse_expression())
					if self.current.typ == TT.RIGHT_PARENTHESIS:
						break
					if self.current.typ != TT.COMMA:
						print(f"ERROR: {self.current.loc}: expected ', ' or ')' ", file=stderr)
						sys.exit(17)
					self.adv()
				self.adv()
				return NodeFunctionCall(name, args)
			return NodeReferTo(name)
		elif self.current == TT.KEYWORD: # intrinsic singletons constants
			name = self.current
			self.adv()
			return NodeIntrinsicConstant(name)
		else:
			print(f"ERROR: {self.current.loc}: Unexpected token while parsing term", file=stderr)
			sys.exit(18)
INTRINSICS:'dict[str,tuple[str,list[Type],Type,int]]' = {
	'print':(
"""
	pop rbx; get ret_addr
	
	pop rsi;put ptr to the correct place
	pop rdx;put len to the correct place
	mov rdi, 1;fd
	mov rax, 1;syscall num
	syscall;print syscall

	push rbx; return ret_addr
	ret
""", [Type.STR, ], Type.VOID, get_id()),
	'exit':(
"""
	pop rbx;get ret addr
	pop rdi;get return_code
	mov rax, 60;syscall number
	syscall;exit syscall
	push rbx; even though it should already exit, return
	ret
""", [Type.INT, ], Type.VOID, get_id()),

	'len':(
"""
	pop rax;get ret addr
	pop rbx;remove str pointer, leaving length
	push rax;push ret addr back
	ret
""", [Type.STR, ], Type.INT, get_id()),

	'ptr':(
"""
	pop rcx

	pop rax;get ptr
	pop rbx;dump length
	push rax;push ptr

	push rcx
	ret
""", [Type.STR, ], Type.PTR, get_id()),
	'str':(
"""
	ret
""", [Type.INT, Type.PTR], Type.STR, get_id()),
	'ptr_to_int':(
"""
	ret
""", [Type.PTR, ], Type.INT, get_id()),
	'int_to_ptr':(
"""
	ret
""", [Type.INT, ], Type.PTR, get_id()),
	'save_int':(
"""
	pop rcx;get ret addr

	pop rbx;get value
	pop rax;get pointer
	mov [rax], rbx; save value to the *ptr

	push rcx;ret addr
	ret
""", [Type.PTR, Type.INT], Type.VOID, get_id()),
	'load_int':(
"""
	pop rbx;get ret addr

	pop rax;get pointer
	push QWORD [rax]

	push rbx;ret addr
	ret
""", [Type.PTR, ], Type.INT, get_id()),
	'save_byte':(
"""
	pop rcx;get ret addr

    pop rbx; get value
    pop rax; get pointer
    mov [rax], bl

	push rcx;ret addr
	ret
""", [Type.PTR, Type.INT], Type.VOID, get_id()),
	'load_byte':(
"""
	pop rcx;get ret addr

	pop rax;get pointer
	xor rbx, rbx; blank space for value
	mov bl, [rax]; read 1 byte and put it into space
	push rbx; push whole number

	push rcx;ret addr
	ret
""", [Type.PTR, ], Type.INT, get_id()),

}
def find_fun_by_name(ast:NodeTops, name:Token) -> NodeFun:
	for top in ast.tops:
		if isinstance(top, NodeFun):
			if top.name == name:
				return top

	print(f"ERROR: {name.loc}: did not find function '{name}'", file=stderr)
	sys.exit(19)
class GenerateAssembly:
	__slots__ = ('strings_to_push','intrinsics_to_add','data_stack','variables','memos','config','ast','file')
	def __init__(self, ast:NodeTops, config:Config) -> None:
		self.strings_to_push   : list[Token]             = []
		self.intrinsics_to_add : set[str]                = set()
		self.data_stack        : list[Type]              = []
		self.variables         : list[NodeTypedVariable] = []
		self.memos             : list[NodeMemo]          = []
		self.config            : Config                  = config
		self.ast               : NodeTops                = ast
		self.generate_assembly()
	def visit_fun(self, node:NodeFun) -> None:
		assert self.variables == [], f"visit_fun called with {self.variables=}"
		self.file.write(f"""
fun_{node.identifier}:;{node.name.operand}
	pop QWORD [r15-8]; save ret pointer
	sub r15,8; make space for ret pointer
""")
		for arg in reversed(node.arg_types):
			self.variables.append(arg)
			self.file.write(f"""
	sub r15, {8*int(arg.typ)} ; make space for arg '{arg.name}' at {arg.name.loc}""")
			for idx in range(int(arg.typ)-1, -1, -1):
				self.file.write(f"""
	pop QWORD [r15+{8*idx}]; save arg""")
			self.file.write('\n')
		self.file.write('\n')
		self.visit(node.code)

		for arg in node.arg_types:
			self.file.write(f"""
	add r15, {8*int(arg.typ)}; remove arg '{arg.name}' at {arg.name.loc}""")
		self.variables = []
		self.file.write("""
	add r15, 8; pop ret addr
	push QWORD [r15-8]; push back ret addr
	ret""")
	def visit_code(self, node:NodeCode) -> None:
		var_before = self.variables.copy()
		for statemnet in node.statements:
			self.visit(statemnet)
		for var in self.variables[len(var_before):]:
			self.file.write(f"""
	add r15, {8*int(var.typ)}; remove var '{var.name}' at {var.name.loc}""")
		self.file.write('\n')
		self.variables = var_before
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
			for _ in top.arg_types:
				self.data_stack.pop()
			self.data_stack.append(top.output_type)
			identifier = f"fun_{top.identifier}"
		self.file.write(f"""
	call {identifier}; call {node.name.operand} at {node.name.loc}
""")
	def visit_token(self, token:Token) -> None:
		if token.typ == TT.DIGIT:
			self.file.write(f"""
    push {token.operand} ; push number {token.loc}
""")
			self.data_stack.append(Type.INT)
		elif token.typ == TT.STRING:
			self.file.write(f"""
	push str_len_{token.identifier} ; push len of string {token.loc}
	push str_{token.identifier} ; push string
""")
			self.strings_to_push.append(token)
			self.data_stack.append(Type.STR)
		else:
			assert False, f"Unreachable: {token.typ=}"
	def visit_bin_exp(self, node:NodeBinaryExpression) -> None:
		self.visit(node.left)
		self.visit(node.right)
		operations = {
TT.PERCENT_SIGN:"""
	xor rdx,rdx
	div rbx
	push rdx
""",
TT.PLUS:"""
	add rax, rbx
	push rax
""",
TT.MINUS:"""
	sub rax, rbx
	push rax
""",
TT.ASTERISK:"""
	mul rbx
	push rax
""",
TT.DOUBLE_SLASH:"""
	xor rdx,rdx
	div rbx
	push rax
""",

TT.GREATER_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovg rdx, rcx
	push rdx
""",
TT.LESS_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovl rdx, rcx
	push rdx
""",
TT.DOUBLE_EQUALS_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmove rdx, rcx
	push rdx
""",
TT.NOT_EQUALS_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovne rdx, rcx
	push rdx
""",
TT.GREATER_OR_EQUAL_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovge rdx, rcx
	push rdx
""",
TT.LESS_OR_EQUAL_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovle rdx, rcx
	push rdx
""",
'and':"""
	and rax,rbx
	push rax
""",
'or':"""
	or rax,rbx
	push rax
""",
'xor':"""
	xor rax,rbx
	push rax
""",
		}
		if node.operation.typ != TT.KEYWORD:
			operation = operations.get(node.operation.typ)
		else:
			operation = operations.get(node.operation.operand)
		assert operation is not None, f"op '{node.operation}' is not implemented yet"
		self.file.write(f"""
	pop rbx; operation '{node.operation}' at {node.operation.loc}
	pop rax{operation}""")
		self.data_stack.pop()#type_check, I count on you
		self.data_stack.pop()
		self.data_stack.append(node.typ)
	def visit_expr_state(self, node:NodeExprStatement) -> None:
		self.visit(node.value)
		self.file.write(f"""
	sub rsp, {8*int(self.data_stack.pop())} ;pop expr result
""")
	def visit_assignment(self, node:NodeAssignment) -> None:
		self.visit(node.value) # get a value to store
		typ = self.data_stack.pop()
		self.variables.append(node.var)
		self.file.write(f"""
	sub r15, {8*int(typ)} ; make space for '{node.var.name}' at {node.var.name.loc}""")
		for idx in range(int(typ)-1, -1, -1):
			self.file.write(f"""
	pop QWORD [r15+{8*idx}] ; save value to the place""")
		self.file.write('\n')
	def get_variable_offset(self,name:Token) -> 'tuple[int,Type]':
		idx = len(self.variables)-1
		offset = 0
		typ = None
		while idx>=0:
			var = self.variables[idx]
			if var.name == name:
				typ = var.typ
				break
			offset+=int(var.typ)
			idx-=1
		else:
			print(f"ERROR: {name.loc}: did not find variable '{name}'", file=stderr)
			sys.exit(20)
		return offset,typ
	def visit_refer(self, node:NodeReferTo) -> None:
		def refer_to_memo(memo:NodeMemo) -> None:
			self.file.write(f"""
	push memo_{memo.identifier}; push PTR to memo at {node.name.loc}
			""")
			self.data_stack.append(Type.PTR)
			return
		def refer_to_variable() -> None:
			offset,typ = self.get_variable_offset(node.name)
			for i in range(int(typ)):
				self.file.write(f'''
		push QWORD [r15+{(offset+i)*8}] ; reference '{node.name}' at {node.name.loc}''')
			self.file.write('\n')
			self.data_stack.append(typ)
		for memo in self.memos:
			if node.name == memo.name:
				return refer_to_memo(memo)
		return refer_to_variable()
	def visit_defining(self, node:NodeDefining) -> None:
		self.variables.append(node.var)
		self.file.write(f"""
	sub r15, {8*int(node.var.typ)} ; defing '{node.var}' at {node.var.name.loc}
""")
	def visit_reassignment(self, node:NodeReAssignment) -> None:
		offset,typ = self.get_variable_offset(node.name)
		self.visit(node.value)
		for i in range(int(typ)-1,-1,-1):
			self.file.write(f'''
	pop QWORD [r15+{(offset+i)*8}]; reassign '{node.name}' at {node.name.loc}''')
		self.file.write('\n')
	def visit_if(self, node:NodeIf) -> None:
		self.visit(node.condition)
		self.file.write(f"""
	pop rax; get condition result of if at {node.loc}
	test rax, rax; test; if true jmp
	jnz if_{node.identifier}; else follow to the else block
""")
		if node.else_code is not None:
			self.visit(node.else_code)
		self.file.write(f"""
	jmp endif_{node.identifier} ; skip if block
if_{node.identifier}:""")
		self.visit(node.code)
		self.file.write(f"""
endif_{node.identifier}:""")
	def visit_intr_constant(self, node:NodeIntrinsicConstant) -> None:
		constants = {
			'False':'push 0',
			'True' :'push 1',
		}
		implementation = constants.get(node.name.operand)
		assert implementation is not None, f"Constant {node.name} is not implemented yet"
		self.file.write(f"""
	{implementation};push constant {node.name}
""")
		self.data_stack.append(node.typ)
	def visit_unary_exp(self, node:NodeUnaryExpression) -> None:
		self.visit(node.right)
		operations = {
			TT.NOT:'xor rax,1'
		}
		implementation = operations.get(node.operation.typ)
		assert implementation is not None, f"Unreachable, {node.operation=}"
		self.file.write(f"""
	pop rax
	{implementation}; perform unary operation '{node.operation}'
	push rax
""")
		self.data_stack.pop()#type_check hello
		self.data_stack.append(node.typ)
	def visit_memo(self, node:NodeMemo) -> None:
		self.memos.append(node)
	def visit(self, node:'Node|Token') -> None:
		if   type(node) == NodeFun              : self.visit_fun          (node)
		elif type(node) == NodeMemo             : self.visit_memo         (node)
		elif type(node) == NodeCode             : self.visit_code         (node)
		elif type(node) == NodeFunctionCall     : self.visit_function_call(node)
		elif type(node) == NodeBinaryExpression : self.visit_bin_exp      (node)
		elif type(node) == NodeUnaryExpression  : self.visit_unary_exp    (node)
		elif type(node) == NodeExprStatement    : self.visit_expr_state   (node)
		elif type(node) == Token                : self.visit_token        (node)
		elif type(node) == NodeAssignment       : self.visit_assignment   (node)
		elif type(node) == NodeReferTo          : self.visit_refer        (node)
		elif type(node) == NodeDefining         : self.visit_defining     (node)
		elif type(node) == NodeReAssignment     : self.visit_reassignment (node)
		elif type(node) == NodeIf               : self.visit_if           (node)
		elif type(node) == NodeIntrinsicConstant: self.visit_intr_constant(node)
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
{INTRINSICS[intrinsic][0]}
""")
			for top in self.ast.tops:
				if isinstance(top, NodeFun):
					if top.name.operand == 'main':
						break
			else:
				print("ERROR: did not find entry point (function 'main')", file=stderr)
				sys.exit(21)
			file.write(f"""
global _start
_start:
	mov [args_ptr], rsp
	mov r15, rsp ; starting fun
	mov rsp, ret_stack_end
	call fun_{top.identifier} ; call main fun
	mov rax, 60
	mov rdi, 0
	syscall
segment .bss
	args_ptr: resq 1
	ret_stack: resb 65536
	ret_stack_end:""")
			for memo in self.memos:
				file.write(f"""
	memo_{memo.identifier}: resb {memo.size}; memo {memo.name} at {memo.name.loc}""")
			file.write("""
segment .data
""")
			for  string in self.strings_to_push:
				if string.operand:
					to_write = ''
					in_quotes = False
					for char in string.operand:
						if safe(char):#ascii
							if in_quotes:
								to_write += char
							else:
								to_write += f'"{char}'
								in_quotes = True
						elif in_quotes:
							to_write += f'", {ord(char)}, '
							in_quotes = False
						else:
							to_write += f'{ord(char)}, '
					if in_quotes:
						to_write += '"'
					else:
						to_write = to_write[:-2]
					length = f'equ $-str_{string.identifier}'
				else:
					to_write = '0'
					length = 'equ 0'
				file.write(f"""
str_{string.identifier}: db {to_write} ; {string.loc}
str_len_{string.identifier}: {length}
""")
def safe(char:str) -> bool:
	if ord(char) > 256: return False
	if char in chars_to_escape: return False
	return True
def run_command(command:'list[str]', config:Config) -> int:
	if not config.silent:
		print(f"[CMD] {' '.join(command)}" )
	return subprocess.call(command)
def run_assembler(config:Config) -> None:
	if not config.run_assembler:
		return
	run:Callable[[list[str]], int] = lambda x:run_command(x, config)
	ret_code = run(['nasm', config.output_file+'.asm', '-f', 'elf64', '-g','-F','dwarf'])
	if ret_code != 0:
		print(f"ERROR: nasm exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(22)
	ret_code = run(['ld', '-o', config.output_file+'.out', config.output_file+'.o'])
	if ret_code != 0:
		print(f"ERROR: GNU linker exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(23)
	ret_code = run(['chmod', '+x', config.output_file+'.out'])
	if ret_code != 0:
		print(f"ERROR: chmod exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(24)
class TypeCheck:
	__slots__ = ('config','ast','variables')
	def __init__(self, ast:NodeTops, config:Config) -> None:
		self.ast = ast
		self.config = config
		self.variables:dict[Token,Type] = {}
		for top in ast.tops:
			self.check(top)
	def check_fun(self, node:NodeFun) -> Type:
		vars_before = self.variables.copy()
		self.variables.update({arg.name:arg.typ for arg in node.arg_types})
		ret_typ = self.check(node.code)
		if node.output_type != ret_typ:
			print(f"ERROR: {node.name.loc}: specified return type ({node.output_type}) does not match actual return type ({ret_typ})",file=stderr)
			sys.exit(25)
		self.variables = vars_before
		return Type.VOID
	def check_code(self, node:NodeCode) -> Type:
		vars_before = self.variables.copy()
		ret = Type.VOID
		for statement in node.statements:
			#@return
			self.check(statement)
		self.variables = vars_before #this is scoping
		return ret
	def check_function_call(self, node:NodeFunctionCall) -> Type:
		intrinsic = INTRINSICS.get(node.name.operand)
		if intrinsic is not None:
			_,input_types,output_type,_ = intrinsic
		else:
			found_node = find_fun_by_name(self.ast,node.name)
			input_types,output_type = [t.typ for t in found_node.arg_types], found_node.output_type
		if len(input_types) != len(node.args):
			print(f"ERROR: {node.name.loc}: function '{node.name}' accepts {len(input_types)} arguments, provided {len(node.args)}",file=stderr)
			sys.exit(26)
		for idx,arg in enumerate(node.args):
			typ = self.check(arg)
			needed = input_types[idx]
			if typ != needed:
				print(f"ERROR: {node.name.loc}: argument {idx} has incompatible type '{typ}', expected '{needed}'",file=stderr)
				sys.exit(27)
		return output_type
	def check_bin_exp(self, node:NodeBinaryExpression) -> Type:
		def bin_op(left_type:Type, right_type:Type) -> Type:
			left = self.check(node.left)
			right = self.check(node.right)
			if left_type == left and right_type == right:
				return node.typ
			print(f"ERROR: {node.operation.loc}: unsupported operation '{node.operation}' for '{right}' and '{left}'",file=stderr)
			sys.exit(28)
		if   node.operation == TT.PLUS                  : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.MINUS                 : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.ASTERISK              : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.DOUBLE_SLASH          : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.PERCENT_SIGN          : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.LESS_SIGN             : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.GREATER_SIGN          : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.DOUBLE_EQUALS_SIGN    : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.NOT_EQUALS_SIGN       : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.LESS_OR_EQUAL_SIGN    : return bin_op(Type.INT, Type.INT)
		elif node.operation == TT.GREATER_OR_EQUAL_SIGN : return bin_op(Type.INT, Type.INT)
		elif node.operation.equals(TT.KEYWORD,'or' ) : return bin_op(Type.BOOL, Type.BOOL)
		elif node.operation.equals(TT.KEYWORD,'xor') : return bin_op(Type.BOOL, Type.BOOL)
		elif node.operation.equals(TT.KEYWORD,'and') : return bin_op(Type.BOOL, Type.BOOL)
		else:
			assert False, f"Unreachable {node.operation=}"
	def check_expr_state(self, node:NodeExprStatement) -> Type:
		self.check(node.value)
		return Type.VOID
	def check_token(self, token:Token) -> Type:
		if   token == TT.STRING : return Type.STR
		elif token == TT.DIGIT  : return Type.INT
		else:
			assert False, f"unreachable {token.typ=}"
	def check_assignment(self, node:NodeAssignment) -> Type:
		actual_type = self.check(node.value)
		if node.var.typ != actual_type:
			print(f"ERROR: {node.var.name.loc}: specified type '{node.var.typ}' does not match actual type '{actual_type}' ",file=stderr)
			sys.exit(29)
		self.variables[node.var.name] = node.var.typ
		return Type.VOID
	def check_refer(self, node:NodeReferTo) -> Type:
		typ = self.variables.get(node.name)
		if typ is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}'", file=stderr)
			sys.exit(30)
		return typ
	def check_defining(self, node:NodeDefining) -> Type:
		self.variables[node.var.name] = node.var.typ
		return Type.VOID
	def check_reassignment(self, node:NodeReAssignment) -> Type:
		actual = self.check(node.value)

		specified = self.variables.get(node.name)
		if specified is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}' (specify type to make new)",file=stderr)
			sys.exit(31)
		if actual != specified:
			print(f"ERROR: {node.name.loc}: variable type ({specified}) does not match type provided ({actual}), to override specify type",file=stderr)
			sys.exit(32)
		return Type.VOID
	def check_if(self, node:NodeIf) -> Type:
		actual = self.check(node.condition)
		if actual != Type.BOOL:
			print(f"ERROR: {node.loc}: if statement expected {Type.BOOL} value, got {actual}",file=stderr)
			sys.exit(33)
		if node.else_code is None:
			return self.check(node.code) #@return
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code) #@return
		assert actual_if == actual_else, "If has incompatible branches error is not written (and should not be possible)"
		return actual_if
	def check_unary_exp(self, node:NodeUnaryExpression) -> Type:
		def unary_op(input_type:Type ) -> Type:
			right = self.check(node.right)
			if input_type == right:
				return node.typ
			print(f"ERROR: {node.operation.loc}: unsupported operation '{node.operation}' for '{right}'",file=stderr)
			sys.exit(34)
		if node.operation == TT.NOT: return unary_op(Type.BOOL)
		else:
			assert False, f"Unreachable, {node.operation=}"
	def check_intr_constant(self, node:NodeIntrinsicConstant) -> Type:
		return node.typ
	
	def check_memo(self, node:NodeMemo) -> Type:
		self.variables[node.name] = Type.PTR
		return Type.VOID
	
	def check(self, node:'Node|Token') -> Type:
		if   type(node) == NodeFun              : return self.check_fun           (node)
		elif type(node) == NodeMemo             : return self.check_memo          (node)
		elif type(node) == NodeCode             : return self.check_code          (node)
		elif type(node) == NodeFunctionCall     : return self.check_function_call (node)
		elif type(node) == NodeBinaryExpression : return self.check_bin_exp       (node)
		elif type(node) == NodeUnaryExpression  : return self.check_unary_exp     (node)
		elif type(node) == NodeIntrinsicConstant: return self.check_intr_constant (node)
		elif type(node) == NodeExprStatement    : return self.check_expr_state    (node)
		elif type(node) == Token                : return self.check_token         (node)
		elif type(node) == NodeAssignment       : return self.check_assignment    (node)
		elif type(node) == NodeReferTo          : return self.check_refer         (node)
		elif type(node) == NodeDefining         : return self.check_defining      (node)
		elif type(node) == NodeReAssignment     : return self.check_reassignment  (node)
		elif type(node) == NodeIf               : return self.check_if            (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
def escape(string:Any) -> str:
	string = f"{string}"
	out = ''
	for char in string:
		out+=chars_to_escape.get(char, char)
	return out
def dump_tokens(tokens:'list[Token]', config:Config) -> None:
	if not config.dump:
		return
	print("TOKENS:" )
	for token in tokens:
		print(f"{token.loc}: \t{token}" )
def dump_ast(ast:NodeTops, config:Config) -> None:
	if not config.dump:
		return
	print("AST:" )
	print(ast)
	sys.exit(0)
def main() -> None:
	config = process_cmd_args(argv)#["me","foo.lang"])
	text = extract_file_text_from_config(config)

	tokens = lex(text, config)
	dump_tokens(tokens, config)

	ast = Parser(tokens, config).parse()
	dump_ast(ast, config)

	TypeCheck(ast,config)

	GenerateAssembly(ast, config)
	run_assembler(config)

	if config.run_file and config.run_assembler:
		ret_code = run_command([f"./{config.output_file}.out"], config)
		sys.exit(ret_code)
	
if __name__ == '__main__':
	main()
