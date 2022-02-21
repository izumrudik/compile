from dataclasses import dataclass
import sys
from sys import stderr
from typing import Any, Callable
import itertools
id_counter = itertools.count()
get_id:Callable[[], int] = lambda:next(id_counter)
NEWLINE = '\n'
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
	' ':' ',
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
	' ':'\\ ',
	'\\':'\\\\'
}
assert len(chars_to_escape) == len(escape_to_chars)
WHITESPACE    = " \t\n\r\v\f\b\a"
DIGITS        = "0123456789"
WORD_FIRST_CHAR_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
WORD_ALPHABET = WORD_FIRST_CHAR_ALPHABET+DIGITS+"]["
KEYWORDS = [
	'fun',
	'memo',
	'const',

	'if',
	'else',
	'elif',
	'return',

	'or',
	'xor',
	'and',

	'True',
	'False',
]

def join(some_list:'list[Any]', sep:str=', ') -> str:
	return sep.join([str(i) for i in some_list])

def safe(char:str) -> bool:
	if ord(char) > 256: return False
	if char in chars_to_escape: return False
	return True

def escape(string:Any) -> str:
	string = f"{string}"
	out = ''
	for char in string:
		out+=chars_to_escape.get(char, char)
	return out

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
					sys.exit(25)
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
				sys.exit(26)

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
					sys.exit(27)
		else:
			if config.get('file') is not None:
				print("ERROR: provided 2 files", file=stderr)
				print(usage(config))
				sys.exit(28)
			config['file'] = arg
		idx+=1
	if config.get('file') is None:
		print("ERROR: file was not provided", file=stderr)
		print(usage(config))
		sys.exit(29)
	if config.get('output_file') is None:
		config['output_file'] = config['file'][:config['file'].rfind('.')]
	return Config(**config)
def extract_file_text_from_config(config:Config) -> str:
	with open(config.file, encoding='utf-8') as file:
		text = file.read()
	return text+'\n'+' '*10
