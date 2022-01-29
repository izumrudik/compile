#!/bin/python3.10
from dataclasses import dataclass,field
from enum import Enum, auto
from sys import argv, stderr
from typing import Callable
@dataclass
class Config:
	self_name:str
	file:str|None = None
	compile_time_rules:list[tuple['Loc',str]] = field(default_factory=list)
	output_file:str = None

def usage(config:Config) -> str:
	return f"""Usage:
	{config.self_name} file [flags]
Flags:
	-h,--help: print this message
"""

def process_cmd_args(args:list[str]) -> Config:
	assert len(args)>0,'Error in the function above'
	self_name = args[0]
	config = Config(self_name)
	args = args[1:]
	idx = 0
	while idx<len(args):
		arg = args[idx]
		match arg[0],arg[1],arg[2:]:
			case '-','-','help':
				print(usage(config))
				exit(0)			
			case '-','-','output':
				idx+=1
				config.output_file = args[idx]
			case '-','O',file:
				config.output_file = file
						
			case '-','-',flag:
				print(f"ERROR: flag {flag} is not supported yet",file=stderr)
				print(usage(self_name))
				exit(1)
			case '-',flag,rest:
				for subflag in flag+rest:#-smth
					match subflag:
						case 'h':
							print(usage(config))
							exit(0)
						case wildcard:
							print(f"ERROR: flag -{wildcard} is not supported yet",file=stderr)
							print(usage(config))
							exit(2)
			case file,rest1,rest2:
				if config.file is not None:
					print(f"ERROR: provided 2 files",file=stderr)
					print(usage(config))
					exit(3)
				file+=rest1+rest2
				config.file = file
		idx+=1
	if config.output_file is None:
		config.output_file = config.file[:config.file.rfind('.')]

	return config

def extract_file_text_from_config(config:Config) -> str:
	if config.file is None:
		print(f"ERROR: file was not provided",file=stderr)
		print(usage(config))
		exit(4)
	with open(config.file,'r') as file:
		text = file.read()
	return text+' '*10

@dataclass
class Loc:
	file_path:str
	file_text:str
	idx:int = 0
	rows:int = 1
	cols:int = 1

	def __add__(self,n):
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
	
	def __repr__(self):
		return f"{self.file_path}:{self.rows}:{self.cols}"

	def __lt__(self,idx):
		return self.idx < idx

	@property
	def char(self):
		return self.file_text[self.idx]
	
	def __bool__(self):
		return self.idx < len(self.file_text)-1


WHITESPACE    = " \t\n\r\v\f"
WORD_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS        = "0123456789"

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
	operand: str | None = None
	
	def __repr__(self) -> str:
		if self.operand is not None:
			return f"{self.operand}"
		return f"{self.typ}"
	
	def eq(self,typ:TT,operand: str | None = None) -> bool:
		return self.typ == typ and self.operand == self.operand

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
					word+={
						'n':'\n',
						't':'\t',
						'v':'\v',
						'r':'\r',
						}.get(loc.char,loc.char)
					loc+=1
					continue
				word+=loc.char
				loc+=1
			programm.append(Token(start_loc,TT.string,word))
			
		elif s in '}{(),;=+-%':
			programm.append(Token(start_loc,
			{
				'{':TT.left_curly_bracket,
				'}':TT.right_curly_bracket,
				'(':TT.left_parenthesis,
				')':TT.right_parenthesis,
				';':TT.semicolon,
				'=':TT.equals_sign,
				'+':TT.plus,
				'-':TT.minus,
				'%':TT.percent_sign,
				',':TT.comma,
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
			loc+=1
			if loc.char == '>':
				programm.append(Token(start_loc,TT.arrow))
			else:
				print(f"ERROR: {loc}: unrecognized sequence: '{s}{loc.char}'",file=stderr)
				exit(9)

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

def join(listik,sep=','):
	return sep.join([repr(i) for i in listik])

class Node:...
@dataclass
class Node_tops(Node):
	tops:list[Node]
	def __repr__(self) -> str:
		newline = '\n'
		return f"{join(self.tops,newline)}"
@dataclass
class Node_function_call(Node):
	name:Token
	args:list[Node|Token]
	def __repr__(self) -> str:
		return f"{self.name}({join(self.args)})"
@dataclass
class Node_binary_expression(Node):
	left:Token | Node
	op:Token
	right:Token | Node
	def __repr__(self) -> str:
		return f"{self.left} {self.op} {self.right}"
@dataclass
class Node_fun(Node):
	name:Token
	input_types:list[Token]
	output_types:list[Token]
	code:"Node_code"
	def __repr__(self) -> str:
		return f"fun {self.name} {join(self.input_types)}->{join(self.output_types)} {self.code}"
@dataclass
class Node_code(Node):
	statements:list[Node]

	def __repr__(self) -> str:
		nl = '\n'
		tab = '\t'
		return f"{'{'}{nl}{tab}{join(self.statements,f';{nl}{tab}')}{nl}{'}'}"

class Parser:
	def __init__(self,words:list[Token],config:Config) -> None:
		self.words = words
		self.config = config
		self.idx=0

	def adv(self):
		"""advance current word"""
		self.idx+=1

	@property
	def current(self):
		return self.words[self.idx]

	def parse(self):
		nodes = []
		while self.current.typ != TT.EOF:
			nodes.append(self.parse_top())
		return Node_tops(nodes)

	def parse_top(self):
		if self.current.eq(TT.keyword,'fun'):
			self.adv()
			if self.current.typ != TT.word:
				print(f"ERROR: {self.current.loc}: expected name of function after keyword 'fun'",file=stderr)
				exit(8)
			name = self.current
			loc = self.current.loc
			self.adv()
			#parse contract of the fun
			input_types = [] 
			while self.current.typ == TT.word: # provided any input types
				raise NotImplementedError()

			output_types = [] 
			if self.current.typ == TT.arrow: # provided any output types
				self.adv()
				while self.current.typ == TT.word:
					raise NotImplementedError()


			code = self.parse_code_block()

			return Node_fun(name,input_types,output_types,code)
		else:
			print(f"ERROR: {self.current.loc}: unrecognized top-level structure while parsing",file=stderr)
			exit(7)
	
	def parse_code_block(self):
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
	def next(self):
		if len(self.words)>self.idx+1:
			return self.words[self.idx+1]

	def parse_statement(self):
		if self.next is not None:
			if self.next.typ == TT.equals_sign:
				raise NotImplementedError()
		
		return self.parse_expression()
		

	def parse_expression(self):
		return self.parse_exp0()

	def bin_exp_parse_helper(self,nexp:Callable[[],Node],operations:tuple[TT]) -> Node:
		left = nexp()
		while self.current.typ in operations:
			op_token = self.current
			self.adv()
			right = nexp()

			left = Node_binary_expression(left,op_token,right)

		return left

	def parse_exp0(self):
		nexp = self.parse_exp1
		return self.bin_exp_parse_helper(nexp,[
			TT.plus,
			TT.minus,
		])
		

	def parse_exp1(self):
		nexp = self.parse_exp2
		return self.bin_exp_parse_helper(nexp,[
			TT.asterisk,
			TT.slash,
		])
	
	def parse_exp2(self):
		nexp = self.parse_term
		return self.bin_exp_parse_helper(nexp,[
			TT.double_asterisk,
			TT.double_slash,
			TT.percent_sign,
		])		
	
	def parse_term(self):
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
			if self.current.typ != TT.left_parenthesis:
				print(f"ERROR: {self.current.loc}: later calling is not allowed yet",file=stderr)
				exit(1000)
				return name #to call later 
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
			
	
	

def type_check(ast,config):
	assert False, " 'type_check' is not implemented yet"


intrinsics = {
	'print':"""
	pop rsi
	pop rdx
	mov rdi, 1
	mov rax, 1
	syscall
"""
}

def compile_to_assembly(ast:Node_tops,config:Config):

	def visit_fun(node:Node_fun):
		file.write(f"""
{node.name.operand}:
	mov [ret_stack_rsp], rsp ; starting fun
	mov rsp, rax

""")
		visit(node.code)
		file.write("""

	mov rax, rsp
	mov rsp, [ret_stack_rsp] ; ending fun
	ret
""")
	def visit_code(node:Node_code):
		for statemnet in node.statements:
			visit(statemnet)
	add_intrinsics_to_code = set()
	def visit_function_call(node:Node_function_call):
		if node.name.operand in intrinsics.keys():
			add_intrinsics_to_code.add(node.name.operand)
		for arg in node.args:
			visit(arg)
		file.write(f"""
	mov rax, rsp
	mov rsp, [ret_stack_rsp]
	call {node.name.operand}
	mov [ret_stack_rsp], rsp
	mov rsp, rax
""")
	strings_to_push = []
	def visit_token(token:Token):
		if token.typ == TT.digit:
			file.write(f"""
    mov rax, {token.operand}
    push rax
""")	
		elif token.typ == TT.string:
			file.write(f"""
	mov rax, {len(token.operand)}
	push rax
	push str_{len(strings_to_push)}
""")
			strings_to_push.append(token.operand)
		else:
			assert False, f"Unreachable: {token.typ=}"
	


	def visit_bin_exp(node:Node_binary_expression):
		assert False, " 'visit_bin_exp' is not implemented yet"
	
	
	def visit(node:Node):
		{
			Node_fun:visit_fun,
			Node_code:visit_code,
			Node_function_call:visit_function_call,
			Node_binary_expression:visit_bin_exp,
			Token:visit_token,
		}[type(node)](node)


	with open(config.output_file + '.asm','w') as file:
		file.write('segment .text')
		for top in ast.tops:
			visit(top)
		for intrinsic in add_intrinsics_to_code:
			file.write(f"""
{intrinsic}:
	mov [ret_stack_rsp], rsp
	mov rsp, rax
{intrinsics[intrinsic]}
	mov rax, rsp
	mov rsp, [ret_stack_rsp]
	ret
""")
		file.write(f"""
global _start
_start:
	mov [args_ptr], rsp
	mov rax, ret_stack_end
	mov [ret_stack_rsp], rax
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
		for idx,string in enumerate(strings_to_push):
			file.write(f"""
str_{idx}: db {','.join([str(ord(i)) for i in string])}
""") 

def run_assembler(config):
	assert False, " 'run_assembler' is not implemented yet"




def main():
	config = process_cmd_args(argv)
	text = extract_file_text_from_config(config)
	tokens = lex(text,config)
	ast = Parser(tokens,config).parse()
	
	
	# later
	#type_check(ast,config) 
	compile_to_assembly(ast,config)
	exit(0)
	run_assembler(config)


	

if __name__ == '__main__':
	main()