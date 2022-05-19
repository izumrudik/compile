import subprocess
from sys import stderr
import sys
import os
from typing import NoReturn
from .core import Config
__all__ = [
	"run_command",
	"replace_self",
	"run_assembler"
]

def run_command(command:list[str], config:Config, put:None|str=None) -> int:
	if config.verbose:
		print(f"CMD: {' '.join(command)}" )
	return subprocess.run(command, input=put, text=True, check=False).returncode
def replace_self(program:'str',args:'list[str]',config:Config) -> NoReturn:
	if config.verbose:
		print(f"INFO: replacing self with '{program} {' '.join(args)}'" )
	args.insert(0,program)
	os.execvp(program, args)
def run_assembler(config:Config, text:str) -> None:
	args = ['opt',  config.optimization, '-o', f'{config.output_file}.bc', '-']
	ret_code = run_command(args,config=config,put=text)
	if ret_code != 0:
		print(f"ERROR: llvm optimizer 'opt' exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(89)
	if config.emit_llvm:
		args = ['llvm-dis', f'{config.output_file}.bc',  '-o', f'{config.output_file}.ll']
		ret_code = run_command(args,config=config)
		if ret_code != 0:
			print(f"ERROR: llvm disassembler 'llvm-dis' exited abnormally with exit code {ret_code}", file=stderr)
			sys.exit(90)
	ret_code = run_command(['clang',config.output_file+'.bc', config.optimization, '-Wno-override-module', '-lgc', '-o', config.output_file+'.out'],config=config)
	if ret_code != 0:
		print(f"ERROR: clang exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(91)
	ret_code = run_command(['chmod', '+x', config.output_file+'.out'],config=config)
	if ret_code != 0:
		print(f"ERROR: chmod exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(92)
