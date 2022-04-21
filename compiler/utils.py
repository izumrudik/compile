import sys
from .primitives import nodes, Token, Config, extract_file_text_from_file_name
from . import lexer
from . import parser
from . import llvm_generator
__all__ = [
	"dump_tokens",
	"dump_module",
	"extract_module_from_file_name",
	"generate_assembly",
]
def dump_module(module:nodes.Module, config:Config) -> None:
	if not config.dump:
		return
	print(module)
	sys.exit(0)
def extract_module_from_file_name(file_name:str, config:Config) -> 'nodes.Module':
	text = extract_file_text_from_file_name(file_name)

	tokens = lexer.lex(text, config, file_name)

	module:nodes.Module = parser.Parser(tokens, config).parse()
	return module

def generate_assembly(module:'nodes.Module', config:Config) -> str:
	generator = llvm_generator.GenerateAssembly(module,config)# no flavours for now
	return generator.text