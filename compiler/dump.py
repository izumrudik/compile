import sys
from .nodes import NodeTops
from .token import Token
from .core import Config

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
