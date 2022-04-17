import subprocess
from sys import stderr
import sys
from typing import Callable
from .core import Config
__all__ = [
	"run_command",
	"run_assembler"
]

def run_command(command:'list[str]', config:Config, put:'None|str'=None) -> int:
	if config.verbose:
		print(f"[CMD] {' '.join(command)}" )

	return subprocess.run(command, input=put, text=True, check=False).returncode
def run_assembler(config:Config) -> None:
	if not config.run_assembler:
		return
	if config.interpret:
		return
	run:Callable[[list[str]], int] = lambda x:run_command(x, config)
	args = ['llc', config.output_file+'.ll', '--filetype=obj', '-opaque-pointers', config.optimization]
	ret_code = run(args)
	if ret_code != 0:
		print(f"ERROR: llvm compiler exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(72)
	ret_code = run(['gcc', '-o', config.output_file+'.out', config.output_file+'.o', config.optimization])
	if ret_code != 0:
		print(f"ERROR: GNU linker exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(73)
	ret_code = run(['chmod', '+x', config.output_file+'.out'])
	if ret_code != 0:
		print(f"ERROR: chmod exited abnormally with exit code {ret_code}", file=stderr)
		sys.exit(74)