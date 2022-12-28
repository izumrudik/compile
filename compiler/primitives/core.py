from dataclasses import dataclass, field
from enum import Enum, auto
import os
import sys
from typing import Callable, NoReturn
import itertools
__all__ = (
	#constants
	"BOOL_TO_STR_CONVERTER",
	"CHARS_TO_ESCAPE",
	"CHAR_TO_STR_CONVERTER",
	"DEFAULT_TEMPLATE_STRING_FORMATTER",
	"DIGITS",
	"DIGITS_BIN",
	"DIGITS_HEX",
	"DIGITS_OCTAL",
	"ESCAPE_TO_CHARS",
	"INT_TO_STR_CONVERTER",
	"JARARACA_PATH",
	"KEYWORDS",
	"NEWLINE",
	"STRING_MULTIPLICATION",
	"WHITESPACE",
	"WORD_ALPHABET",
	"WORD_FIRST_CHAR_ALPHABET",
	'BUILTIN_WORDS',
	"id_counter",
	#functions
	"get_id",
	"escape",
	"process_cmd_args",
	"extract_file_text_from_file_path",
	"pack_directory",
	#classes
	"Loc",
	"Config",
	"ET",
	"Error",
	"ErrorBin",
	"ErrorExit",
)
KEYWORDS = (
	'fun',
	'use',
	'from',
	'const',
	'import',
	'typedef',
	'struct',
	'enum',
	'var',
	'mix',
	'as',

	'if',
	'elif',
	'else',
	'while',
	'return',
	'default',
	'assert',
	'match',
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
	'\\':'\\',
	'`':'`',
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
	'\\':'\\\\',
	'`':'`',
}
MAIN_MODULE_PATH = '__main__'
DEFAULT_TEMPLATE_STRING_FORMATTER = 'default_template_string_formatter'
CHAR_TO_STR_CONVERTER = 'char_to_str'
INT_TO_STR_CONVERTER = 'int_to_str'
BOOL_TO_STR_CONVERTER = 'bool_to_str'
STRING_MULTIPLICATION = 'string_multiplication_provider'
ASSERT_FAILURE_HANDLER = 'assert_failure_handler'
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
	'put',
	'eput',
	'putn',
	'eputn',
	'fputendl',
	'putendl',
	'eputendl',
	'parse_int',
	'stdin',
	'stdout',
	'stderr',
	'read',
	'puts',
	'eputs',

	'i64',
	'i32',
	'i8',
	'byte',
	'min',
	'max',
	DEFAULT_TEMPLATE_STRING_FORMATTER,
	BOOL_TO_STR_CONVERTER,
	INT_TO_STR_CONVERTER,
	CHAR_TO_STR_CONVERTER,
	STRING_MULTIPLICATION,
	ASSERT_FAILURE_HANDLER,
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


@dataclass(slots=True, frozen=True)
class Loc:
	file_path:str
	idx:int
	line:int = field(compare=False, repr=False)
	cols:int = field(compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.file_path}:{self.line}:{self.cols}"

@dataclass(slots=True, frozen=True)
class Place:
	start:Loc
	end:Loc
	def __post_init__(self) -> None:
		assert self.start.file_path == self.end.file_path, "Mismatch between 'start' and 'end' locs in 'Place'"
	@property
	def file_path(self) -> str:
		assert self.start.file_path == self.end.file_path, "Mismatch between 'start' and 'end' locs in 'Place'"
		return self.start.file_path
	@property
	def length(self) -> int:
		return self.end.idx - self.start.idx
	def __str__(self) -> str:
		assert self.start.file_path == self.end.file_path, "Mismatch between 'start' and 'end' locs in 'Place'"
		return f"{self.start}"

class ErrorExit(SystemExit):
	pass

class ET(Enum):# Error Type
	ARRAY_SUBSCRIPT     = auto()
	ARRAY_SUBSCRIPT_LEN = auto()
	ASSIGNMENT          = auto()
	BIN_OP              = auto()
	BLOCK_START         = auto()
	CALLABLE            = auto()
	CALL_ARG            = auto()
	CALL_ARGS           = auto()
	CALL_COMMA          = auto()
	CALL_MIX            = auto()
	CAST                = auto()
	CAST_COMMA          = auto()
	CAST_LPAREN         = auto()
	CAST_RPAREN         = auto()
	CHARACTER           = auto()
	CHMOD               = auto()
	CIRCULAR_IMPORT     = auto()
	CLANG               = auto()
	CMD_FILE            = auto()
	CMD_FLAG            = auto()
	CMD_OUTPUT_NAME     = auto()
	CMD_O_NAME          = auto()
	CMD_PACK_NAME       = auto()
	CMD_SUBFLAG         = auto()
	COLON               = auto()
	CONST_NAME          = auto()
	CTE_TERM            = auto()
	CTE_ZERO_DIV        = auto()
	CTE_ZERO_MOD        = auto()
	DECLARATION_BRACKET = auto()
	DECLARATION_TIMES   = auto()
	DIR                 = auto()
	DIVISION            = auto()
	DOT                 = auto()
	DOT_ENUM            = auto()
	DOT_ENUM_KIND       = auto()
	DOT_MODULE          = auto()
	DOT_STRUCT          = auto()
	DOT_STRUCT_KIND     = auto()
	ENUM_FUN_ARG        = auto()
	ENUM_FUN_ARGS       = auto()
	ENUM_NAME           = auto()
	ENUM_STR_MAGIC      = auto()
	ENUM_STR_MAGIC_RET  = auto()
	ENUM_VALUE          = auto()
	EOF                 = auto()
	EXPR_PAREN          = auto()
	FIELD_NAME          = auto()
	FROM_2NAME          = auto()
	FROM_IMPORT         = auto()
	FROM_NAME           = auto()
	FUNCTION_TYPE_ARROW = auto()
	FUN_COMMA           = auto()
	FUN_NAME            = auto()
	FUN_PAREN           = auto()
	FUN_RETURN          = auto()
	FUN_TYP_COMMA       = auto()
	IF                  = auto()
	IF_BRANCH           = auto()
	ILLEGAL_CHAR        = auto()
	ILLEGAL_NUMBER      = auto()
	IMPORT_NAME         = auto()
	INIT_MAGIC          = auto()
	INIT_MAGIC_RET      = auto()
	LLVM_DIS            = auto()
	MAIN_ARGS           = auto()
	MAIN_RETURN         = auto()
	MATCH               = auto()
	MATCH_ARROW         = auto()
	MATCH_AS            = auto()
	MATCH_CASE_NAME     = auto()
	MATCH_DEFAULT       = auto()
	MATCH_ENUM          = auto()
	MATCH_NAME          = auto()
	MIX_MIXED_NAME      = auto()
	MIX_NAME            = auto()
	MODULE              = auto()
	MODULE_NAME         = auto()
	NEWLINE             = auto()
	OPT                 = auto()
	PACKET              = auto()
	PACKET_NAME         = auto()
	REFER               = auto()
	RETURN              = auto()
	SAVE                = auto()
	SAVE_PTR            = auto()
	SET_EQUALS          = auto()
	SET_NAME            = auto()
	SIZED_DECLARATION   = auto()
	SIZED_VSAVE         = auto()
	STRUCT_FUN_ARG      = auto()
	STRUCT_FUN_ARGS     = auto()
	STRUCT_NAME         = auto()
	STRUCT_STATEMENT    = auto()
	STRUCT_STATICS      = auto()
	STRUCT_STR_MAGIC    = auto()
	STRUCT_SUBSCRIPT    = auto()
	STRUCT_SUB_LEN      = auto()
	STRUCT__STR__RET    = auto()
	STR_ANY_CHAR        = auto()
	STR_CAST_LEN        = auto()
	STR_CAST_PTR        = auto()
	STR_SUBSCRIPT       = auto()
	STR_SUBSCRIPT_LEN   = auto()
	SUBSCRIPT           = auto()
	SUBSCRIPT_COMMA     = auto()
	SUBSCRIPT_MAGIC     = auto()
	TEMPLATE_ANY_CHAR   = auto()
	TEMPLATE_ARG0       = auto()
	TEMPLATE_ARG1       = auto()
	TEMPLATE_ARG2       = auto()
	TEMPLATE_ARGS       = auto()
	TEMPLATE_DR_CURLY   = auto()
	TEMPLATE_FUN        = auto()
	TEMPLATE_R_CURLY    = auto()
	TERM                = auto()
	TOP                 = auto()
	TOP_NEWLINE         = auto()
	TYPE                = auto()
	TYPEDEF_EQUALS      = auto()
	TYPEDEF_NAME        = auto()
	TYPED_VAR_NAME      = auto()
	TYPE_REFERENCE      = auto()
	UNARY_OP            = auto()
	USE_ARROW           = auto()
	USE_AS_NAME         = auto()
	USE_COMMA           = auto()
	USE_NAME            = auto()
	USE_PAREN           = auto()
	VAR_NAME            = auto()
	VSAVE               = auto()
	VSAVE_PTR           = auto()
	WHILE               = auto()
	WORD_REF            = auto()
	ARRAY_BRACKET       = auto()
	ASSERT_VALUE        = auto()
	ASSERT_EXPLANATION  = auto()
	def __str__(self) -> str:
		return f"{self.name.lower().replace('_','-')}"
@dataclass(slots=True, frozen=True)
class ErrorBin:
	silent:bool = False
	errors:'list[Error]' = field(default_factory=list)
	def add_error(self, err:ET,place:'Place|None',msg:'str') -> None:
		self.errors.append(Error(place,err,msg))
		return None

	def show_errors(self) -> None|NoReturn:
		if len(self.errors) == 0:
			return None
		self.crash_with_errors()

	def crash_with_errors(self) -> NoReturn:
		assert len(self.errors) != 0, "crash_with_errors should be called only with errors"
		if not self.silent:
			for error in self.errors:
				print(f"{error}", file=sys.stderr, flush=True)
		if len(self.errors) >= 256:
			raise ErrorExit(1)
		else:
			raise ErrorExit(len(self.errors))

	def critical_error(self, err:ET,place:'Place|None', msg:'str') -> NoReturn:
		self.errors.append(Error(place,err,msg))
		self.crash_with_errors()

	def exit_properly(self, code:int = 0) -> NoReturn:
		self.show_errors()
		sys.exit(code)
@dataclass(slots=True, frozen=True)
class Error:
	place:'Place|None'
	typ:ET
	msg:str
	def __str__(self) -> str:
		loc = f"{self.place}: " if self.place is not None else ''
		return f"\x1b[91mERROR:\x1b[0m {loc}{self.msg} [{self.typ}]"

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
	file          : str
	output_file   : str
	run_file      : bool
	verbose       : bool
	emit_llvm     : bool
	dump          : bool
	interpret     : bool
	optimization  : str
	argv          : list[str]
	assume_assert : bool
	errors        : ErrorBin
	@property
	def silent(self) ->bool:
		return self.errors.silent
	@classmethod
	def use_defaults(
		cls,
		errors        : ErrorBin,
		file          : str,
		*,
		output_file   : None|str       = None,
		run_file      : None|bool      = None,
		verbose       : None|bool      = None,
		emit_llvm     : None|bool      = None,
		dump          : None|bool      = None,
		interpret     : None|bool      = None,
		optimization  : None|str       = None,
		argv          : None|list[str] = None,
		assume_assert : None|bool      = None,
	) -> 'Config':
		if output_file   is None: output_file   = file[:file.rfind('.')]
		if run_file      is None: run_file      = False
		if run_file      is None: run_file      = False
		if verbose       is None: verbose       = False
		if emit_llvm     is None: emit_llvm     = False
		if dump          is None: dump          = False
		if interpret     is None: interpret     = False
		if optimization  is None: optimization  = '-O2'
		if argv          is None: argv          = []
		if assume_assert is None: assume_assert = False
		return cls(
			file,
			output_file,
			run_file,
			verbose,
			emit_llvm,
			dump,
			interpret,
			optimization,
			argv,
			assume_assert,
			errors
		)

def process_cmd_args(eb:ErrorBin,args:list[str]) -> Config:
	assert len(args)>0, 'Error in the function above'
	self_name = args[0]
	file          = None
	output_file   = None
	run_file      = None
	verbose       = None
	emit_llvm     = None
	dump          = None
	interpret     = None
	optimization  = None
	argv          = None
	assume_assert = None
	args = args[1:]
	idx = 0
	while idx<len(args):
		arg = args[idx]
		if arg[:2] == '--':
			flag = arg[2:]
			if flag == 'help':
				usage(eb, self_name)
			elif flag == 'output':
				idx+=1
				if idx>=len(args):
					eb.critical_error(ET.CMD_OUTPUT_NAME,None,'expected file name after --output option (-h for help)')
				output_file = args[idx]
			elif flag == 'pack':
				idx+=1
				if idx>=len(args):
					eb.critical_error(ET.CMD_PACK_NAME,None,'expected directory path after --pack option (-h for help)')
				pack_directory(args[idx])
				eb.exit_properly(0)
			elif flag == 'verbose':
				verbose = True
			elif flag == 'emit-llvm':
				emit_llvm = True
			elif flag == 'dump':
				dump = True
			elif flag == 'assume':
				assume_assert = True
			else:
				eb.add_error(ET.CMD_FLAG,None,f"flag '--{flag}' is not supported yet")
		elif arg[:2] =='-o':
			idx+=1
			if idx>=len(args):
				eb.critical_error(ET.CMD_O_NAME,None,'expected file name after -o option (-h for help)')
			output_file = args[idx]
		elif arg in ('-O0','-O1','-O2','-O3'):
			optimization = arg
		elif arg[0] == '-':
			for subflag in arg[1:]:
				if subflag == 'h':
					usage(eb, self_name)
				elif subflag == 'r':
					run_file = True
				elif subflag == 'v':
					verbose = True
				elif subflag == 'i':
					interpret = True
				elif subflag == 'l':
					emit_llvm = True
				else:
					eb.add_error(ET.CMD_SUBFLAG,None,f"subflag '-{subflag}' is not supported yet")
		else:
			file = arg
			idx+=1
			break
		idx+=1
	argv = args[idx:]
	if file is None:
		eb.critical_error(ET.CMD_FILE,None,'file was not provided')
	return Config.use_defaults(
		eb,
		file          = file,
		output_file   = output_file,
		run_file      = run_file,
		verbose       = verbose,
		emit_llvm     = emit_llvm,
		dump          = dump,
		interpret     = interpret,
		optimization  = optimization,
		argv          = argv,
		assume_assert = assume_assert,
	)
def usage(eb:ErrorBin,self_name:str|None) -> NoReturn:
	eb.show_errors()
	print(
f"""Usage:
	{self_name or '<program>'} file [flags]
Notes:
	short versions of flags can be combined for example `-r -v` can be shorten to `-rv`
Flags:
	-h --help      : print this message
	-i             : use lli to interpret bytecode
	-r             : run compiled program
	-o --output    : specify output file `-o name` (do not combine short version)
	-v --verbose   : generate debug output
	   --dump      : dump ast of the program
	-l --emit-llvm : emit llvm ir
	-O0 -O1        : optimization levels (last overrides)
	-O2 -O3        : default is -O2
	   --pack      : specify a directory to pack into a discoverable packet (ignore any other flags)
	   --assume    : removes assertion checking and assumes that all assertions are true, uses it for optimization
"""
	)
	eb.exit_properly(0)
def extract_file_text_from_file_path(file_name:str) -> str:
	with open(file_name, encoding='utf-8') as file:
		text = file.read()
	return text+'\n'

