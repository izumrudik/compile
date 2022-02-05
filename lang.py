#!/bin/python
from dataclasses import dataclass,field
from collections import deque as Stack
from enum import Enum, auto
import subprocess
from sys import argv, stderr
from typing import Any, Callable

@dataclass
class Config:
	self_name          : str
	file               : str
	output_file        : str
	compile_time_rules : list[tuple['Loc',str]] = field(default_factory=list)
	run_file           : bool                   = False
	silent             : bool                   = False
	run_assembler      : bool                   = True	
	dump               : bool                   = False

def usage(config:dict[str,str]) -> str:
	return f"""Usage:
	{config.get('self_name','programm')} file [flags]
Flags:
	-h,--help   : print this message
	-O,--output : specify output file (do not combine this flag)
	-r          : run compiled programm 
	-s          : don't generate any non-error output generated by compiler
	-n          : do not run assembler and linker (overrides -r)
	--dump      : dump tokens and ast of the programm
"""

def process_cmd_args(args:list[str]) -> Config:
	assert len(args)>0,'Error in the function above'
	self_name = args[0]
	config:dict[str,Any] = {'self_name':self_name}
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
					print("ERROR: expected file name after --output option",file=stderr)
					print(usage(config))
					exit(17)
				config['output_file'] = args[idx]
			elif flag == 'silent':
				config['silent'] = True
			elif flag == 'dump':
				config['dump'] = True
			else:	
				print(f"ERROR: flag {flag} is not supported yet",file=stderr)
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
					print(f"ERROR: flag -{subflag} is not supported yet",file=stderr)
					print(usage(config))
					exit(2)

		else:
			if config.get('file') is not None:
				print(f"ERROR: provided 2 files",file=stderr)
				print(usage(config))
				exit(3)
			config['file'] = arg
		idx+=1

	if config.get('file') is None:
		print(f"ERROR: file was not provided",file=stderr)
		print(usage(config))
		exit(4)
	if config.get('output_file') is None:
		config['output_file'] = config['file'][:config['file'].rfind('.')]


	return Config(**config)

def extract_file_text_from_config(config:Config) -> str:
	with open(config.file,'r') as file:
		text = file.read()
	return text+'\n'+' '*10

@dataclass
class Loc:
	file_path:str
	file_text:str
	idx:int = 0
	rows:int = 1
	cols:int = 1

	def __add__(self,n:int) -> 'Loc':
		idx,cols,rows = self.idx,self.cols,self.rows
		if idx+n>=len(self.file_text):
			print(f"ERROR: {self}: unexpected end of file",file=stderr)
			exit(5)
		for _ in range(n):
			idx+=1
			cols+=1
			if self.file_text[idx] =='\n':
				cols = 0
				rows+= 1
		return type(self)(self.file_path,self.file_text,idx,rows,cols)
	
	def __repr__(self) -> str:
		return f"{self.file_path}:{self.rows}:{self.cols}"

	def __lt__(self,idx:int) -> bool:
		return self.idx<idx

	@property
	def char(self) -> str:
		return self.file_text[self.idx]
	
	def __bool__(self) -> bool:
		return self.idx < len(self.file_text)-1

WHITESPACE    = " \t\n\r\v\f\b\a"
WORD_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
DIGITS        = "0123456789"

typ = int # I did not implemented types yet

keywords = [
	'fun'
]
class TT(Enum):
	digit               = auto()
	word                = auto()
	keyword             = auto()
	left_curly_bracket  = auto()
	right_curly_bracket = auto()
	left_parenthesis    = auto()
	right_parenthesis   = auto()
	string              = auto()
	EOF                 = auto()
	arrow               = auto()
	semicolon           = auto()
	colon               = auto()
	comma               = auto()
	equals_sign         = auto()
	plus                = auto()
	minus               = auto()
	asterisk            = auto()
	double_asterisk     = auto()
	slash               = auto()
	double_slash        = auto()
	percent_sign        = auto()
@dataclass
class Token:
	loc:Loc
	typ:TT
	operand: str = ''
	
	def __repr__(self) -> str:
		if self.operand !='':
			return escape(self.operand)
		return escape(self.typ)
	
	def eq(self,typ_or_token:'TT|Token',operand: str | None = None) -> bool:
		if isinstance(typ_or_token,Token):
			operand = typ_or_token.operand
			typ_or_token = typ_or_token.typ
		return self.typ == typ_or_token and self.operand == operand

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, TT|Token):
			return NotImplemented
		return self.eq(other)
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

def lex(text:str,config:Config) -> list[Token]:
	loc=Loc(config.file,text,)
	programm:list[Token] = []
	while loc:
		s = loc.char
		start_loc = loc
		if s in WHITESPACE:
			loc+=1
			continue

		elif s in DIGITS:
			word = s
			loc+=1
			while loc.char in DIGITS:
				word+=loc.char
				loc+=1
			programm.append(Token(start_loc,TT.digit,word))
			continue

		elif s in WORD_ALPHABET:
			word = s
			loc+=1

			while loc.char in WORD_ALPHABET:
				word+=loc.char
				loc+=1
			
			programm.append(Token(start_loc,
			TT.keyword if word in keywords else TT.word
			,word))
			continue
			
		elif s in "'\"":
			loc+=1
			word = ''
			while loc.char != s:
				if loc.char == '\\':
					loc+=1
					word+=escape_to_chars.get(loc.char,loc.char)
					loc+=1
					continue
				word+=loc.char
				loc+=1
			programm.append(Token(start_loc,TT.string,word))
			
		elif s in '}{(),;=+%:':
			programm.append(Token(start_loc,
			{
				'{':TT.left_curly_bracket,
				'}':TT.right_curly_bracket,
				'(':TT.left_parenthesis,
				')':TT.right_parenthesis,
				';':TT.semicolon,
				'=':TT.equals_sign,
				'+':TT.plus,
				'%':TT.percent_sign,
				',':TT.comma,
				':':TT.colon,
			}[s]))


		elif s == '*':
			token = Token(start_loc,TT.asterisk)
			loc+=1
			if loc.char == '*':
				loc+=1
				token = Token(start_loc,TT.double_asterisk)
			programm.append(token)
			continue

		elif s == '/':
			token = Token(start_loc,TT.slash)
			loc+=1
			if loc.char == '/':
				token = Token(start_loc,TT.double_slash)
				loc+=1
			programm.append(token)
			continue

		elif s == '-':
			token = Token(start_loc,TT.minus)
			loc+=1
			if loc.char == '>':
				token = Token(start_loc,TT.arrow)
			programm.append(token)
		elif s == '#':
			while loc.char != '\n':
				loc+=1
			continue
		elif s == '!':
			word = ''
			while loc.char != '\n':
				word+=loc.char
				loc+=1
			config.compile_time_rules.append((start_loc,word))
			continue
		else:
			print(f"ERROR: {loc}: Illigal char '{s}'",file=stderr)
			exit(6)
		loc+=1
	programm.append(Token(start_loc,TT.EOF))
	return programm

def join(listik:list[Any],sep:str=',') -> str:
	return sep.join([repr(i) for i in listik])

def tab(s:str) -> str:
	return s.replace('\n','\n\t')
class Node:
	pass
@dataclass
class Node_tops(Node):
	tops:list[Node]
	def __repr__(self) -> str:
		sep = ',\n\n'
		return f"[\n\t{tab(join(self.tops,sep))}\n]"
@dataclass
class Node_function_call(Node):
	name:Token
	args:list[Node|Token]
	def __repr__(self) -> str:
		return f"{self.name}({join(self.args)})" 
@dataclass
class Node_expr_statement(Node):
	value:Node | Token
	def __repr__(self) -> str:
		return f"{self.value}"
@dataclass
class Node_assignment(Node):
	name:Token
	typ:Token
	value:Node|Token
	def __repr__(self) -> str:
		return f"{self.name}:{self.typ} = {self.value}"

@dataclass
class Node_refer_to(Node):
	name:Token
	def __repr__(self) -> str:
		return f"{self.name}"
@dataclass
class Node_binary_expression(Node):
	left:Token | Node
	op:Token
	right:Token | Node
	def __repr__(self) -> str:
		return f"({self.left} {self.op} {self.right})"
@dataclass
class Node_fun(Node):
	name:Token
	input_types:list[typ]
	output_types:list[typ]
	code:"Node_code"
	def __repr__(self) -> str:
		return f"fun {self.name} {join(self.input_types)}->{join(self.output_types)} {self.code}"
@dataclass
class Node_code(Node):
	statements:list[Node | Token]

	def __repr__(self) -> str:
		nl = '\n'
		tab = '\t'
		return f"{'{'}{nl}{tab}{join(self.statements,f';{nl}{tab}')}{nl}{'}'}"

class Parser:
	def __init__(self,words:list[Token],config:Config) -> None:
		self.words = words
		self.config = config
		self.idx=0

	def adv(self) -> None:
		"""advance current word"""
		self.idx+=1

	@property
	def current(self) -> Token:
		return self.words[self.idx]

	def parse(self) -> Node_tops:
		nodes = []
		while self.current.typ != TT.EOF:
			nodes.append(self.parse_top())
		return Node_tops(nodes)

	def parse_top(self) -> Node:
		if self.current.eq(TT.keyword,'fun'):
			self.adv()
			if self.current.typ != TT.word:
				print(f"ERROR: {self.current.loc}: expected name of function after keyword 'fun'",file=stderr)
				exit(8)
			name = self.current
			loc = self.current.loc
			self.adv()
			#parse contract of the fun
			input_types:list[typ] = [] 
			while self.current.typ == TT.word: # provided any input types
				raise NotImplementedError()

			output_types:list[typ] = [] 
			if self.current.typ == TT.arrow: # provided any output types
				self.adv()
				while self.current.typ == TT.word:
					raise NotImplementedError()


			code = self.parse_code_block()

			return Node_fun(name,input_types,output_types,code)
		else:
			print(f"ERROR: {self.current.loc}: unrecognized top-level structure while parsing",file=stderr)
			exit(7)
	
	def parse_code_block(self) -> Node_code:
		if self.current.typ != TT.left_curly_bracket:
			print(f"ERROR: {self.current.loc}: expected code block starting with '{'{'}' ",file=stderr)
			exit(10)
		self.adv()
		code=[]
		while self.current.typ != TT.right_curly_bracket:
			code.append(self.parse_statement()) 
			if self.current.typ == TT.right_curly_bracket:break
			if self.current.typ != TT.semicolon:
				print(f"ERROR: {self.current.loc}: expected ';' or '{'}'}' ",file=stderr)
				exit(11)
			self.adv()
		self.adv()
		return Node_code(code)	
		
	@property
	def next(self) -> Token | None:
		if len(self.words)>self.idx+1:
			return self.words[self.idx+1]
		return None
	
	def parse_statement(self) -> Node|Token:
		if self.next is not None:
			if self.next.typ == TT.colon:
				name,typ = self.parse_typed_variable()
				if self.current.typ != TT.equals_sign:
					print(f"ERROR: {self.current.loc}: expected '=' after typed name",file=stderr)
					exit(19)
				self.adv()
				value = self.parse_expression()
				return Node_assignment(name,typ,value)
		return Node_expr_statement(self.parse_expression())

	def parse_typed_variable(self) -> tuple[Token,Token]:
		name = self.current
		self.adv()#colon
		assert self.current.typ == TT.colon, "bug in function above ^, or in this one"	
		self.adv()#type
		typ = self.parse_type()
		
		return name,typ	
	
	def parse_type(self) -> Token:
		out = self.current # for now that is enough
		self.adv()
		return out
	
	def parse_expression(self) -> Node | Token:
		return self.parse_exp0()

	def bin_exp_parse_helper(self,nexp:Callable[[],Node|Token],operations:list[TT]) -> Node | Token:
		left = nexp()
		while self.current.typ in operations:
			op_token = self.current
			self.adv()
			right = nexp()

			left = Node_binary_expression(left,op_token,right)

		return left

	def parse_exp0(self) -> Node | Token:
		nexp = self.parse_exp1
		return self.bin_exp_parse_helper(nexp,[
			TT.plus,
			TT.minus,
		])
		

	def parse_exp1(self) -> Node | Token:
		nexp = self.parse_exp2
		return self.bin_exp_parse_helper(nexp,[
			TT.asterisk,
			TT.slash,
		])
	
	def parse_exp2(self) -> Node | Token:
		nexp = self.parse_term
		return self.bin_exp_parse_helper(nexp,[
			TT.double_asterisk,
			TT.double_slash,
			TT.percent_sign,
		])		
	
	def parse_term(self) -> Node | Token:
		if self.current.typ in (TT.digit,TT.string):
			token = self.current
			self.adv()
			return token
		if self.current.typ == TT.left_parenthesis:
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.right_parenthesis:
				print(f"ERROR: {self.current.loc}: expected '('",file=stderr)
				exit(12)
			self.adv()
			return expr
		if self.current.typ == TT.word: #trying to extract function call
			name = self.current
			self.adv()
			if self.current.typ == TT.left_parenthesis:
				 
				self.adv()
				args = []
				while self.current.typ != TT.right_curly_bracket:
					args.append(self.parse_expression()) 
					if self.current.typ == TT.right_parenthesis:break
					if self.current.typ != TT.comma:
						print(f"ERROR: {self.current.loc}: expected ',' or ')' ",file=stderr)
						exit(13)
					self.adv()
				self.adv()
				return Node_function_call(name,args)
			return Node_refer_to(name)
		else:
			print(f"ERROR: {self.current.loc}: Unexpexted token while parsing term")
			exit(18)

INTRINSICS = {
	'print':
"""
	pop rsi;print syscall
	pop rdx
	mov rdi, 1
	mov rax, 1
	syscall
"""
}

class Generator:
	def __init__(self,ast:Node_tops,config:Config) -> None:
		self.strings_to_push:list[Token] = []
		self.intrinsics_to_add:set[str] = set()
		self.number_of_values_stack:list[typ] = []
		self.variables:list[tuple[Token,typ]] = []
		self.config:Config = config
		self.ast = ast

	def visit_fun(self,node:Node_fun) -> None:
		self.file.write(f"""
{node.name.operand}:
	mov [ret_stack_rsp], rsp ; starting fun
	mov rsp, rax ; swapping back ret_stack and data_stack 

""")
		self.visit(node.code)
		self.file.write(f"""

	mov rax, rsp; swapping ret_stack and data_stack 
	mov rsp, [ret_stack_rsp] ; ending fun""")
		for tok,i in self.variables:
			for _ in range(i):
				self.file.write(f"""
	pop rbx; remove variable '{tok}' at {tok.loc}""")
		self.file.write('\n\tret')
	
	def visit_code(self,node:Node_code) -> None:
		for statemnet in node.statements:
			self.visit(statemnet)
	
	def visit_function_call(self,node:Node_function_call) -> None:
		if node.name.operand in INTRINSICS.keys():
			self.intrinsics_to_add.add(node.name.operand)
		for arg in node.args:
			self.visit(arg)
		self.file.write(f"""
	mov rax, rsp ; call function 
	mov rsp, [ret_stack_rsp] ; {node.name.loc}
	call {node.name.operand}
	mov [ret_stack_rsp], rsp
	mov rsp, rax
""")
		#placeholder for now
		self.number_of_values_stack.append(0)
		# TODO: function can return something diffrent
	
	def visit_token(self,token:Token) -> None:
		if token.typ == TT.digit:
			self.file.write(f"""
    push {token.operand} ; push number {token.loc}
""")		
			self.number_of_values_stack.append(1)
		elif token.typ == TT.string:
			self.file.write(f"""
	push {len(token.operand)} ; push string {token.loc}
	push str_{len(self.strings_to_push)}
""")
			self.strings_to_push.append(token)
			self.number_of_values_stack.append(2)
		else:
			assert False, f"Unreachable: {token.typ=}"
	
	def visit_bin_exp(self,node:Node_binary_expression) -> None:
		self.visit(node.left)
		self.visit(node.right)
		operations:dict[TT,str] = {
		TT.plus:'add',
		TT.minus:'sub',
		}
		op = operations.get(node.op.typ)
		if op is None:
			print(f"ERROR: {node.op.loc}: op {node.op} is not implemented yet")
			exit(-1)
		self.file.write(f"""
	pop rax; operating {node.op} at {node.op.loc}
	pop rbx
	{op} rax,rbx
	push rax
""")
		self.number_of_values_stack.pop()
		self.number_of_values_stack.pop()
		self.number_of_values_stack.append(1)

	
	def visit_expr_state(self,node:Node_expr_statement) -> None:
		self.visit(node.value)
		self.file.write("""
	pop rax ;pop expr result"""*
	self.number_of_values_stack.pop())
		self.file.write('\n\n')

	def visit_assignment(self,node:Node_assignment) -> None:
		self.visit(node.value) # get a value to store
		l = self.number_of_values_stack.pop()
		self.variables.append((node.name,l))
		self.file.write(f"""
	mov rax, [ret_stack_rsp] ; assign '{node.name}'
	sub rax, {l*8} ; at {node.name.loc}
	mov [ret_stack_rsp], rax""")
		for idx in range(l-1,-1,-1):
			self.file.write(f"""
	pop rbx
	mov [rax+{idx*8}],rbx""")
		self.file.write('\n')

	def visit_referer(self,node:Node_refer_to) -> None:
		idx = len(self.variables)-1
		offset = 0
		while idx>=0:
			var = self.variables[idx]
			if var[0].eq(node.name):
				length = var[1]
				break
			offset+=var[1]
			idx-=1
		else:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}'",file=stderr)
			exit(9)
		self.file.write(f'''
	mov rax, [ret_stack_rsp]; refrence '{node.name}' at {node.name.loc}''')
		for i in range(length):
			self.file.write(f'''
	push QWORD [rax+{(offset+i)*8}]''')
		self.file.write('\n')
		self.number_of_values_stack.append(length)
	def visit(self,node:Node|Token) -> None:
		if   type(node) == Node_fun              : self.visit_fun          (node)
		elif type(node) == Node_code             : self.visit_code         (node)
		elif type(node) == Node_function_call    : self.visit_function_call(node)
		elif type(node) == Node_binary_expression: self.visit_bin_exp      (node)
		elif type(node) == Node_expr_statement   : self.visit_expr_state   (node)
		elif type(node) == Token                 : self.visit_token        (node)
		elif type(node) == Node_assignment       : self.visit_assignment   (node)
		elif type(node) == Node_refer_to         : self.visit_referer      (node)
		else:
			assert False, f'Unreachable, unknown {type(node)=} '
		return None
	
	def generate_assembly(self) -> None:	 
		with open(self.config.output_file + '.asm','w') as file:
			self.file = file
			file.write('segment .text')
			for top in self.ast.tops:
				self.visit(top)
			for intrinsic in self.intrinsics_to_add:
				file.write(f"""
{intrinsic}: ;intrinsic 
	mov [ret_stack_rsp], rsp
	mov rsp, rax;default
{INTRINSICS[intrinsic]}
	mov rax, rsp;default
	mov rsp, [ret_stack_rsp]
	ret
""")
			file.write(f"""
global _start
_start:
	mov [args_ptr], rsp
	mov rax, ret_stack_end
	mov [ret_stack_rsp], rax ; default stuff
	call main
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
			for idx,string in enumerate(self.strings_to_push):
				file.write(f"""
str_{idx}: db {','.join([str(ord(i)) for i in string.operand])} ; {string.loc}
""") 
		return None

def run_command(command:list[str],config:Config) -> int:
	if not config.silent:
		print(f"[CMD] {' '.join(command)}")
	return subprocess.call(command)

def run_assembler(config:Config) -> None:
	run:Callable[[list[str]],int] = lambda x:run_command(x,config)
	ret_code = run(['nasm',config.output_file+'.asm','-f','elf64'])
	if ret_code != 0:
		print(f"ERROR: nasm exited abnormaly with exit code {ret_code}",file=stderr)
		exit(14)

	ret_code = run(['ld','-o',config.output_file+'.out',config.output_file+'.o'])
	if ret_code != 0:
		print(f"ERROR: GNU linker exited abnormaly with exit code {ret_code}",file=stderr)
		exit(15)
	
	ret_code = run(['chmod','+x',config.output_file+'.out'])
	if ret_code != 0:
		print(f"ERROR: chmod exited abnormaly with exit code {ret_code}",file=stderr)
		exit(16)
	return None
	
def type_check(ast:Node_tops,config:Config) -> None:
	assert False, " 'type_check' is not implemented yet"

def escape(string:Any) -> str:
	string = f"{string}"
	out = ''
	for char in string:
		out+=chars_to_escape.get(char,char)
	return out

def dump_tokens(tokens:list[Token],config:Config) -> None:
	print("Tokens:")
	for token in tokens:
		print(f"\t{token.loc}: \t{token}")
	return None

def dump_ast(ast:Node_tops,config:Config) -> None:
	print("Ast:")
	print(ast)
	return None

def main() -> None:
	config = process_cmd_args(argv)
	text = extract_file_text_from_config(config)
	tokens = lex(text,config)
	if config.dump:
		dump_tokens(tokens,config)
	ast = Parser(tokens,config).parse()
	if config.dump:
		dump_ast(ast,config)
		exit(0)
	Generator(ast,config).generate_assembly()
	if not config.run_assembler:
		exit(0)
	run_assembler(config)
	if config.run_file:
		ret_code = run_command([config.output_file+'.out'],config)
		exit(ret_code)










if __name__ == '__main__':
	main()