from dataclasses import dataclass, field
from enum import Enum, auto
import os
import sys
from sys import stderr
from typing import Callable, ClassVar, NoReturn
import itertools
__all__ = (
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
	'BUILTIN_WORDS',
	"id_counter",
	#functions
	"get_id",
	"escape",
	"usage",
	"process_cmd_args",
	"extract_file_text_from_file_name",
	"pack_directory",
	"show_errors",
	"add_error",
	"create_critical_error",
	"exit_properly",
	#classes
	"Loc",
	"Config",
	"ET",
	"Error",
)
KEYWORDS = (
	'fun',
	'use',
	'from',
	'const',
	'import',
	'struct',
	'mix',

	'if',
	'else',
	'elif',
	'while',
	'return',
	'set',

	'or',
	'xor',
	'and',

	'True',
	'False',
	'Null',
	'Argv',
	'Argc',
	'Void',
)
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
BUILTIN_WORDS = (
	'ptr',
	'len',
	'str',
	'int',
	'char',
	'short',
	'get_arg',
	'nth_bit',
	'exit',
	'fputs',
	'puts',
	'eputs',
	'putch',
	'putendl',
	'putsln',
	'putd',
	'parse_int',
	'allocate',
	'Array',

	'stdin',
	'stdout',
	'stderr',
	'read',
)
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


__all__

class ET(Enum):# Error Type
	ANY_CHAR = auto()
	CHARACTER = auto()
	DIVISION = auto()
	ILLEGAL_CHAR = auto()
	NO_USE_NAME = auto()
	NO_USE_PAREN = auto()
	NO_USE_COMMA = auto()
	NO_CONST_NAME = auto()
	NO_FROM_IMPORT = auto()
	NO_FROM_NAME = auto()
	NO_FROM_2NAME = auto()
	NO_STRUCT_NAME = auto()
	NO_MIX_NAME = auto()
	UNRECOGNIZED_TOP = auto()
	NO_MIX_MIXED_NAME = auto()
	NO_PACKET_NAME = auto()
	NO_PACKET = auto()
	NO_DIR = auto()
	NO_MODULE_NAME = auto()
	NO_MODULE = auto()
	RECURSION = auto()
	NO_GENERIC_PERCENT = auto()
	NO_GENERIC_NAME = auto()
	NO_FUN_NAME = auto()
	NO_FUN_PAREN = auto()
	NO_FUN_COMMA = auto()
	UNRECOGNIZED_STRUCT_STATEMENT = auto()
	UNRECOGNIZED_CTE_TERM = auto()
	CTE_ZERO_DIV = auto()
	CTE_ZERO_MOD = auto()
	NO_DECLARATION_BRACKET = auto()
	NO_SET_NAME = auto()
	NO_SET_EQUALS = auto()
	NO_TYPED_VAR_NAME = auto()
	NO_COLON = auto()
	NO_ARRAY_BRACKET = auto()
	NO_SUBSCRIPT_BRACKET = auto()
	NO_NEWLINE = auto()
	NO_CALL_COMMA = auto()
	NO_BLOCK_START = auto()
	NO_WORD_REF = auto()
	UNRECOGNIZED_TYPE = auto()
	NO_GENERIC_COMMA = auto()
	NO_EXPR_PAREN = auto()
	NO_CAST_RPAREN = auto()
	NO_CAST_COMMA = auto()
	NO_GENERIC_TYPE_NAME = auto()
	NO_FIELD_NAME = auto()
	NO_CAST_LPAREN = auto()
	NO_FUN_TYP_COMMA = auto()
	NO_TERM = auto()
	UNEXPECTED_EOF = auto()
	BIN_OP = auto()
	UNARY_OP = auto()
	DOT_STRUCT = auto()
	DOT_STRUCT_KIND = auto()
	NO_MAGIC = auto()
	UNRECOGNIZED_CTE_OP = auto()
	def __str__(self) -> str:
		return f"{self.name.lower().replace('_','-')}"
@dataclass(slots=True, frozen=True)
class Loc:
	file_path:str
	idx :int = field()
	rows:int = field(compare=False, repr=False)
	cols:int = field(compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.file_path}:{self.rows}:{self.cols}"

@dataclass(slots=True, frozen=True)
class Error:
	loc:'Loc'
	typ:ET
	msg:str
	errors:'ClassVar[list[Error]]' = []
def add_error(err:ET,loc:'Loc',msg:'str') -> None|NoReturn:
	Error.errors.append(Error(loc,err,msg))
	if len(Error.errors) >= 254: 
		# 255s is reserved if there is critical error
		# this branch is here to prevent having >= 256 errors
		# which means you can't sys.exit(len(Error.errors)) meaningfully
		crash_with_errors()
	return None

def show_errors() -> None|NoReturn:
	if len(Error.errors) == 0:
		return None
	crash_with_errors()

def crash_with_errors() -> NoReturn:
	assert len(Error.errors) != 0, "crash_with_errors should be called only with errors"

	for error in Error.errors:
		print(f"ERROR: {error.loc} {error.msg} [{error.typ}]", file=sys.stderr, flush=True)

	if len(Error.errors) >= 256:
		sys.exit(1)
	else:
		sys.exit(len(Error.errors))

def create_critical_error(err:ET,loc:'Loc', msg:'str') -> NoReturn:
	Error.errors.append(Error(loc,err,msg))
	crash_with_errors()

def exit_properly(code:int) -> NoReturn:
	show_errors()
	sys.exit(code)

def pack_directory(directory:str) -> None:
	name = os.path.basename(directory)
	path = os.path.join(JARARACA_PATH,'packets')
	with open(os.path.join(path,name+'.link'), 'w', encoding='utf-8') as file:
		file.write(os.path.abspath(directory))


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
				exit_properly(0)
			elif flag == 'output':
				idx+=1
				if idx>=len(args):
					print("ERROR: expected file name after --output option", file=stderr)
					print(usage(config))
					sys.exit(99)
				config.output_file = args[idx]
			elif flag == 'pack':
				idx+=1
				if idx>=len(args):
					print("ERROR: expected directory path after --pack option", file=stderr)
					print(usage(config))
					sys.exit(100)
				pack_directory(args[idx])
				exit_properly(0)
			elif flag == 'verbose':
				config.verbose = True
			elif flag == 'emit-llvm':
				config.emit_llvm = True
			elif flag == 'dump':
				config.dump = True
			else:
				print(f"ERROR: flag '{flag}' is not supported yet", file=stderr)
				print(usage(config))
				sys.exit(101)
		elif arg[:2] =='-o':
			idx+=1
			if idx>=len(args):
				print("ERROR: expected file name after -o option", file=stderr)
				print(usage(config))
				sys.exit(102)
			config.output_file = args[idx]
		elif arg in ('-O0','-O1','-O2','-O3'):
			config.optimization = arg
		elif arg[0] == '-':
			for subflag in arg[1:]:
				if subflag == 'h':
					print(usage(config))
					exit_properly(0)
				elif subflag == 'r':
					config.run_file = True
				elif subflag == 'v':
					config.verbose = True
				elif subflag == 'i':
					config.interpret = True
				elif subflag == 'l':
					config.emit_llvm = True
				else:
					print(f"ERROR: flag '-{subflag}' is not supported yet", file=stderr)
					print(usage(config))
					sys.exit(103)
		else:
			config.file = arg
			idx+=1
			break
		idx+=1
	config.argv = args[idx:]
	if config.file is None:
		print("ERROR: file was not provided", file=stderr)
		print(usage(config))
		sys.exit(104)
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

