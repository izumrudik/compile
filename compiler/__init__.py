from sys import argv
import sys
from .primitives import process_cmd_args, run_assembler, run_command
from .type_checker import TypeCheck
from .parser import Parser
from .utils import  extract_ast_from_file_name, dump_ast, dump_tokens, generate_assembly
def main() -> None:
	config = process_cmd_args(argv)#["me", "foo.ja"])
	tokens, ast = extract_ast_from_file_name(config.file,config)
	dump_tokens(tokens, config)
	dump_ast(ast, config)

	TypeCheck(ast, config)

	txt = generate_assembly(ast, config)
	run_assembler(config)
	if config.interpret:
		ret_code = run_command(["lli","-opaque-pointers",config.optimization,'--fake-argv0',f"'{config.file}'",'-',*config.argv],config,put=txt)
		sys.exit(ret_code)
	if config.run_file and config.run_assembler:
		ret_code = run_command([f"./{config.output_file}.out",*config.argv], config)
		sys.exit(ret_code)

if __name__ == '__main__':
	main()
