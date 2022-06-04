import subprocess
import os
from typing import NoReturn
from .core import Config, add_error, show_errors, critical_error, ET
__all__ = [
	"run_command",
	"replace_self",
	"run_assembler"
]

def run_command(command:list[str], config:Config, put:None|str=None) -> int:
	show_errors()
	if config.verbose:
		print(f"CMD: {' '.join(command)}" )
	return subprocess.run(command, input=put, text=True, check=False).returncode
def replace_self(args:'list[str]',config:Config) -> NoReturn:
	show_errors()
	if config.verbose:
		print(f"INFO: handing execution to '{' '.join(args)}' (execvp)" )
	os.execvp(args[0], args)
def run_assembler(config:Config, text:str) -> None:
	args = ['opt',  config.optimization, '-o', f'{config.output_file}.bc', '-']
	ret_code = run_command(args,config=config,put=text)
	if ret_code != 0:
		critical_error(ET.OPT, None, "llvm optimizer 'opt' exited abnormally with exit code {ret_code} (use -v to see invocation)")
	if config.emit_llvm:
		args = ['llvm-dis', f'{config.output_file}.bc',  '-o', f'{config.output_file}.ll']
		ret_code = run_command(args,config=config)
		if ret_code != 0:
			add_error(ET.LLVM_DIS, None, f"llvm disassembler 'llvm-dis' exited abnormally with exit code {ret_code} (use -v to see invocation)")
	ret_code = run_command(['clang',config.output_file+'.bc', config.optimization, '-Wno-override-module', '-lgc', '-o', config.output_file+'.out'],config=config)
	if ret_code != 0:
		critical_error(ET.CLANG,None,f"clang exited abnormally with exit code {ret_code} (use -v to see invocation)")
	ret_code = run_command(['chmod', '+x', config.output_file+'.out'],config=config)
	if ret_code != 0:
		critical_error(ET.CHMOD, None, f"chmod exited abnormally with exit code {ret_code} (use -v to see invocation)")
