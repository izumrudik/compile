from sys import argv
import sys
from .lexer import lex
from .primitives import process_cmd_args, run_assembler, run_command
from .parser import Parser
from .type_checker import TypeCheck
from .generator import GenerateAssembly
from .utils import  extract_ast_from_file_name, dump_ast, dump_tokens
def main() -> None:
	config = process_cmd_args(argv)#["me", "foo.lang"])
	tokens, ast = extract_ast_from_file_name(config.file,config)
	dump_tokens(tokens, config)
	dump_ast(ast, config)

	TypeCheck(ast, config)

	GenerateAssembly(ast, config)
	run_assembler(config)
	if config.run_file and config.run_assembler:
		ret_code = run_command([f"./{config.output_file}.out"], config)
		sys.exit(ret_code)
	
if __name__ == '__main__':
	main()
