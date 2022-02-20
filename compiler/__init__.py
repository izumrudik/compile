from sys import argv
import sys
from .lexer import lex
from .core import process_cmd_args,extract_file_text_from_config
from .dump import dump_ast,dump_tokens
from .parser import Parser
from .type_checker import TypeCheck
from .generator import GenerateAssembly
from .run import run_assembler,run_command

def main() -> None:
	config = process_cmd_args(argv)#["me","foo.lang"])
	text = extract_file_text_from_config(config)

	tokens = lex(text, config)
	dump_tokens(tokens, config)

	ast = Parser(tokens, config).parse()
	dump_ast(ast, config)

	TypeCheck(ast,config)

	GenerateAssembly(ast, config)
	run_assembler(config)
	if config.run_file and config.run_assembler:
		ret_code = run_command([f"./{config.output_file}.out"], config)
		sys.exit(ret_code)
	
if __name__ == '__main__':
	main()
