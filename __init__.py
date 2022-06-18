import os
os.environ['JARARACA_PATH'] = os.path.dirname(os.path.realpath(__file__))
del os
__all__ = (
	"Config",
	"Lexer",
	"Parser",
	"type_check",
	"ErrorBin",
	"ErrorExit"
)
from .compiler.lexer import Lexer
from .compiler.parser import Parser
from .compiler.type_checker import type_check
from .compiler.primitives import Config, ErrorBin, ErrorExit
