#!/bin/python3.10
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache as cache
from sys import argv, stderr
#exit>9
@dataclass
class Config:
	self_name:str
	file:str|None = None

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
	for arg in args:
		match arg[0],arg[1],arg[2:]:
			case '-','-','help':
				print(usage(config))
				exit(0)
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
	return config

def extract_file_text_from_config(config:Config) -> str:
	if config.file is None:
		print(f"ERROR: file was not provided",file=stderr)
		print(usage(config))
		exit(4)
	with open(config.file,'r') as file:
		text = file.read()
	return text+' '*10
@cache
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
			print(f"ERROR: {self}: unexpected end of file")
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
@dataclass
class Token:
	loc:Loc
	typ:TT
	operand: str | None = None
	
	def __repr__(self) -> str:
		return f"{self.loc}\t{self.typ}({self.operand})"
	
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
					continue
				word+=loc.char
				loc+=1
			programm.append(Token(start_loc,TT.string,word))
			
		elif s in '}{()':
			programm.append(Token(start_loc,
			{
				'{':TT.left_curly_bracket,
				'}':TT.right_curly_bracket,
				'(':TT.left_parenthesis,
				')':TT.right_parenthesis,
			}[s]))

		elif s == '-':
			loc+=1
			if loc.char == '>':
				programm.append(Token(start_loc,TT.arrow))
			else:
				print(f"ERROR: {loc}: unrecognized sequence: '{s}{loc.char}'")
				exit(9)

		elif s == '#':
			while loc.char != '\n':
				loc+=1
			continue

		else:
			print(f"ERROR: {loc}: Illigal char '{s}'")
			exit(6)
		loc+=1
	return programm





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
			nodes.append(self.parse_lvl0())
		return nodes

	def parse_lvl0(self):
		if self.current.eq(TT.keyword,'fun'):
			self.adv()
			if self.current.typ != TT.word:
				print(f"ERROR: {self.current.loc}: expected name of function after keyword 'fun'")
				exit(8)
			name = self.current
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

			if self.current.typ == TT.left_curly_bracket:
				...

			
		else:
			print(f"ERROR: {self.current.loc}: unrecognized top-level structure while parsing")
			exit(7)
	


def type_check(ast,config):
	assert False, " 'type_check' is not implemented yet"

def compile_to_assembly(ast,config):
	assert False, " 'compile_to_assembly' is not implemented yet"

def run_assembler(config):
	assert False, " 'run_assembler' is not implemented yet"




def main():
	config = process_cmd_args(argv)
	text = extract_file_text_from_config(config)
	tokens = lex(text,config)
	for token in tokens: print(token)
	ast = Parser(tokens,config).parse()
	print(ast)
	exit(0)
	type_check(ast,config)
	compile_to_assembly(ast,config)
	run_assembler(config)


	

if __name__ == '__main__':
	main()