from dataclasses import dataclass, field
import os
import sys
from sys import stderr
from typing import Callable
import itertools
__all__ = [
	#constants
	"JARARACA_PATH",
	"NEWLINE",
	"WHITESPACE",
	"DIGITS",
	"DIGITS_HEX",
	"DIGITS_BIN",
	"DIGITS_OCTAL",
	"WORD_FIRST_CHAR_ALPHABET",
	"WORD_ALPHABET",
	"ESCAPE_TO_CHARS",
	"CHARS_TO_ESCAPE",
	"KEYWORDS",
	"id_counter",
	#functions
	"get_id",
	"safe",
	"escape",
	"usage",
	"process_cmd_args",
	"extract_file_text_from_file_name",
	"pack_directory",
	"Config",
]
KEYWORDS = [
	'fun',
	'use',
	'from',
	'const',
	'import',
	'struct',
	'var',
	'mix',

	'if',
	'else',
	'elif',
	'while',
	'return',

	'or',
	'xor',
	'and',

	'True',
	'False',
	'Null',
	'Argv',
	'Argc',
]
ESCAPE_TO_CHARS = {
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
CHARS_TO_ESCAPE = {
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
assert len(CHARS_TO_ESCAPE) == len(ESCAPE_TO_CHARS)
JARARACA_PATH = os.environ['JARARACA_PATH']
NEWLINE       = '\n'
WHITESPACE    = " \t\n\r\v\f\b\a"
DIGITS        = "0123456789"
DIGITS_HEX    = "0123456789AaBbCcDdEeFf" 
DIGITS_BIN    = "01"
DIGITS_OCTAL  = "01234567"
WORD_FIRST_CHAR_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
WORD_ALPHABET = WORD_FIRST_CHAR_ALPHABET+DIGITS

id_counter = itertools.count()
get_id:Callable[[], int] = lambda:next(id_counter)

def pack_directory(directory:str) -> None:
	name = os.path.basename(directory)
	path = os.path.join(JARARACA_PATH,'packets')
	with open(os.path.join(path,name+'.link'), 'w', encoding='utf-8') as file:
		file.write(os.path.abspath(directory))


def safe(char:str) -> bool:
	if ord(char) > 256: return False
	if char in CHARS_TO_ESCAPE: return False
	return True

def escape(string:str) -> str:
	out = ''
	for char in string:
		out+=CHARS_TO_ESCAPE.get(char, char)
	return out

@dataclass(slots=True, frozen=True)
class Config:
	self_name    : str
	file         : str
	output_file  : str
	run_file     : bool
	verbose      : bool
	emit_llvm    : bool
	dump         : bool
	interpret    : bool
	optimization : str
	argv         : list[str]
@dataclass(slots=True)
class __Config_draft:
	self_name    : str
	file         : str|None = None
	output_file  : str|None = None
	run_file     : bool     = False
	verbose      : bool     = False
	emit_llvm    : bool     = False
	dump         : bool     = False
	interpret    : bool     = False
	optimization : str      = '-O2'
	argv         : list[str]= field(default_factory=list)
def process_cmd_args(args:list[str]) -> Config:
	assert len(args)>0, 'Error in the function above'
	self_name = args[0]
	config:__Config_draft = __Config_draft(self_name)
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
					sys.exit(69)
				config.output_file = args[idx]
			elif flag == 'pack':
				idx+=1
				if idx>=len(args):
					print("ERROR: expected directory path after --pack option", file=stderr)
					print(usage(config))
					sys.exit(70)
				pack_directory(args[idx])
				sys.exit(0)
			elif flag == 'verbose':
				config.verbose = True
			elif flag == 'emit-llvm':
				config.emit_llvm = True
			elif flag == 'dump':
				config.dump = True
			else:
				print(f"ERROR: flag {flag} is not supported yet", file=stderr)
				print(usage(config))
				sys.exit(71)
		elif arg[:2] =='-o':
			idx+=1
			if idx>=len(args):
				print("ERROR: expected file name after -o option", file=stderr)
				print(usage(config))
				sys.exit(72)
			config.output_file = args[idx]
		elif arg in ('-O0','-O1','-O2','-O3'):
			config.optimization = arg
		elif arg[0] == '-':
			for subflag in arg[1:]:
				if subflag == 'h':
					print(usage(config))
					sys.exit(0)
				elif subflag == 'r':
					config.run_file = True
				elif subflag == 'v':
					config.verbose = True
				elif subflag == 'i':
					config.interpret = True
				elif subflag == 'l':
					config.emit_llvm = True
				else:
					print(f"ERROR: flag -{subflag} is not supported yet", file=stderr)
					print(usage(config))
					sys.exit(73)
		else:
			config.file = arg
			idx+=1
			break
		idx+=1
	config.argv = args[idx:]
	if config.file is None:
		print("ERROR: file was not provided", file=stderr)
		print(usage(config))
		sys.exit(74)
	if config.output_file is None:
		config.output_file = config.file[:config.file.rfind('.')]
	return Config(
		self_name     = config.self_name,
		file          = config.file,
		output_file   = config.output_file,
		run_file      = config.run_file,
		verbose       = config.verbose,
		emit_llvm     = config.emit_llvm,
		dump          = config.dump,
		interpret     = config.interpret,
		optimization  = config.optimization,
		argv          = config.argv,
	)
def usage(config:__Config_draft) -> str:
	return f"""Usage:
	{config.self_name or 'program'} file [flags]
Notes:
	short versions of flags can be combined for example `-r -v` can be shorten to `-rv`
Flags:
	-h --help      : print this message
	-o --output    : specify output file `-o name` (do not combine short version)
	-r             : run compiled program
	-v --verbose   : generate debug output
	   --dump      : dump ast of the program
	-i             : use lli to interpret bitecode
	-l --emit-llvm : emit llvm ir
	-O0 -O1        : optimization levels last one overrides previous ones
	-O2 -O3        : default is -O2
	   --pack      : specify directory to pack it into discoverable packet (ignore any other flags)
"""
def extract_file_text_from_file_name(file_name:str) -> str:
	with open(file_name, encoding='utf-8') as file:
		text = file.read()
	if text[0] == '\n':
		text = ' ' + text
	return text+'\n '

