import sys
from .primitives import nodes, Config, extract_file_text_from_file_name
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

parsed_modules:dict[str, nodes.Module] = {}
def extract_module_from_file_name(file_name:str, config:Config, module_path:str) -> 'nodes.Module':
	if module_path in parsed_modules:
		return parsed_modules[module_path]
	if config.verbose:
		print(f"INFO: Extracting module '{module_path}' from file '{file_name}'")
	text = extract_file_text_from_file_name(file_name)
	tokens = lexer.lex(text, config, file_name)
	module:nodes.Module = parser.Parser(tokens, config, module_path).parse()
	parsed_modules[module_path] = module
	return module

