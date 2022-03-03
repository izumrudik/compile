from dataclasses import dataclass, field
from enum import Enum, auto
from sys import stderr
import sys
from .core import escape, get_id
__all__ = [
	'Token',
	'Loc',
	'TT',
]
@dataclass(frozen=True, order=True)
class Loc:
	file_path:str
	idx :int = field()
	rows:int = field(compare=False, repr=False)
	cols:int = field(compare=False, repr=False)
	def __str__(self) -> str:
		return f"{self.file_path}:{self.rows}:{self.cols}"
@dataclass(frozen=True, order=True)
class draft_loc:
	file_path:str
	file_text:str = field(compare=False, repr=False)
	idx:int    = 0
	rows:int = field(default=1, compare=False, repr=False)
	cols:int = field(default=1, compare=False, repr=False)
	def __add__(self, number:int) -> 'draft_loc':
		idx, cols, rows = self.idx, self.cols, self.rows
		if idx+number>=len(self.file_text):
			print(f"ERROR: {self}: unexpected end of file", file=stderr)
			sys.exit(46)
		for _ in range(number):
			idx+=1
			cols+=1
			if self.file_text[idx] =='\n':
				cols = 0
				rows+= 1
		return self.__class__(self.file_path, self.file_text, idx, rows, cols)
	def __str__(self) -> str:
		return f"{self.file_path}:{self.rows}:{self.cols}"

	@property
	def char(self) -> str:
		return self.file_text[self.idx]
	def __bool__(self) -> bool:
		return self.idx < len(self.file_text)-1
	
	def to_loc(self) -> Loc:
		return Loc(
			file_path=self.file_path,
			idx=self.idx,
			rows=self.rows,
			cols=self.cols
		)
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
	DOUBLE_LESS_SIGN      = auto()
	DOUBLE_GREATER_SIGN   = auto()
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
			TT.DOUBLE_GREATER_SIGN:'>>',
			TT.DOUBLE_LESS_SIGN:'<<',
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
		return names.get(self, self.name.lower())
@dataclass(frozen=True, eq=False)
class Token:
	loc:Loc = field(compare=False)
	typ:TT
	operand:str = ''
	identifier:int = field(default_factory=get_id, compare=False, repr=False)
	def __str__(self) -> str:
		if self.typ == TT.STRING:
			return f'"{escape(self.operand)}"'
		if self.operand !='':
			return escape(self.operand)
		return escape(str(self.typ))
	def equals(self, typ_or_token:'TT|Token', operand:'str|None' = None) -> bool:
		if isinstance(typ_or_token, Token):
			operand = typ_or_token.operand
			typ_or_token = typ_or_token.typ
			return self.typ == typ_or_token and self.operand == operand
		if operand is None:
			return self.typ == typ_or_token
		return self.typ == typ_or_token and self.operand == operand

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, (TT, Token)):
			return NotImplemented
		return self.equals(other)

	def __hash__(self) -> int:
		return hash((self.typ, self.operand))