from os import path
from sys import argv
from typing import NoReturn


from .primitives import JARARACA_PATH, process_cmd_args, run_assembler, replace_self, pack_directory, id_counter, ErrorBin
from .parser import Parser
from .type_checker import type_check
from .llvm_generator import GenerateAssembly
from .utils import  extract_module_from_file_name, dump_module

pack_directory(path.join(JARARACA_PATH, 'std'))
def main() -> NoReturn:
	eb = ErrorBin()
	config = process_cmd_args(eb, argv)
	eb.show_errors()

	module = extract_module_from_file_name(config.file,config)
	if config.verbose:
		eb.show_errors()
		print(f"INFO: Conversion to ast step completed with id counter state '{id_counter}'")
	dump_module(module, config)
	type_check(module, config)
	eb.show_errors()

	txt = GenerateAssembly(module,config).text
	eb.show_errors()

	run_assembler(config,txt)
	eb.show_errors()

	if config.interpret:
		replace_self(["lli",config.optimization, '-load', 'libgc.so', '--fake-argv0',f"{config.file}",f'{config.output_file}.bc',*config.argv],config)
	if config.run_file:
		replace_self([f"{config.output_file}.out"]+config.argv, config)

	eb.exit_properly(0)
if __name__ == '__main__':
	main()
