from os import path
from sys import argv
from .primitives import JARARACA_PATH, process_cmd_args, run_assembler, replace_self, pack_directory
from .type_checker import TypeCheck
from .parser import Parser
from .llvm_generator import GenerateAssembly
from .utils import  extract_module_from_file_name, dump_module
def main() -> None:
	pack_directory(path.join(JARARACA_PATH, 'std'))
	config = process_cmd_args(argv)#["me", "foo.ja"])
	module = extract_module_from_file_name(config.file,config,'__main__')
	dump_module(module, config)

	TypeCheck(module, config)

	txt = GenerateAssembly(module,config).text

	run_assembler(config,txt)
	if config.interpret:
		replace_self("lli", [config.optimization, '-load', 'libgc.so', '--fake-argv0',f"'{config.file}'",f'{config.output_file}.bc',*config.argv],config)
	if config.run_file:
		replace_self(f"{config.output_file}.out",config.argv, config)

if __name__ == '__main__':
	main()
