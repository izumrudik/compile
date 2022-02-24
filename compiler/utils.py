#pylint:disable=C0116
import sys
from .primitives import nodes, Token, Config, extract_file_text_from_file_name
from . import lexer
from . import parser
def dump_tokens(tokens:'list[Token]', config:Config) -> None:
	if not config.dump:
		return
	print("TOKENS:" )
	for token in tokens:
		print(f"{token.loc}: \t{token}" )
def dump_ast(ast:nodes.Tops, config:Config) -> None:
	if not config.dump:
		return
	print("AST:" )
	print(ast)
	sys.exit(0)
def extract_ast_from_file_name(file_name:str, config:Config) -> 'tuple[list[Token],nodes.Tops]':
	text = extract_file_text_from_file_name(file_name)

	tokens = lexer.lex(text, config)

	ast:nodes.Tops = parser.Parser(tokens, config).parse()
	return tokens, ast
