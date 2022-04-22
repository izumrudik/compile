from os import path
from sys import argv
import sys


from .primitives import JARARACA_PATH, process_cmd_args, run_assembler, run_command, pack_directory
from .type_checker import TypeCheck
from .parser import Parser
from .llvm_generator import GenerateAssembly
from .utils import  extract_module_from_file_name, dump_module
def main() -> None:
	pack_directory(path.join(JARARACA_PATH, 'std'))
	config = process_cmd_args(argv)#["me", "foo.ja"])
	module = extract_module_from_file_name(config.file,config,'__main__','<[main module]>')
	dump_module(module, config)

	TypeCheck(module, config)

	txt = GenerateAssembly(module,config).text
	with open(config.output_file + '.ll', 'wt', encoding='UTF-8') as file:
		file.write(txt)

	run_assembler(config)
	if config.interpret:
		ret_code = run_command(["lli","-opaque-pointers",config.optimization,'--fake-argv0',f"'{config.file}'",'-',*config.argv],config,put=txt)
		sys.exit(ret_code)
	if config.run_file and config.run_assembler:
		ret_code = run_command([f"./{config.output_file}.out",*config.argv], config)
		sys.exit(ret_code)

if __name__ == '__main__':
	main()
