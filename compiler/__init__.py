from os import path
from sys import argv
from typing import NoReturn

from .primitives import JARARACA_PATH, process_cmd_args, run_assembler, replace_self, pack_directory, id_counter, exit_properly, show_errors
from .parser import Parser
from .type_checker import TypeCheck
from .llvm_generator import GenerateAssembly
from .utils import  extract_module_from_file_name, dump_module

def main() -> NoReturn:
	pack_directory(path.join(JARARACA_PATH, 'std'))
	config = process_cmd_args(argv)
	show_errors()

	module = extract_module_from_file_name(config.file,config,'__main__')
	if config.verbose:
		show_errors()
		print(f"INFO: Conversion to ast step completed with id counter state '{id_counter}'")
	dump_module(module, config)
	TypeCheck(module, config)
	show_errors()

	txt = GenerateAssembly(module,config).text
	show_errors()

	run_assembler(config,txt)
	show_errors()

	if config.interpret:
		replace_self(["lli",config.optimization, '-load', 'libgc.so', '--fake-argv0',f"{config.file}",f'{config.output_file}.bc',*config.argv],config)
	if config.run_file:
		replace_self([f"{config.output_file}.out"]+config.argv, config)

	exit_properly(0)
if __name__ == '__main__':
	main()
