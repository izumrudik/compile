import subprocess
from sys import stderr
import sys
from typing import Callable
from .core import Config
__all__ = [
	"run_command",
	"run_assembler"
]

def run_command(command:'list[str]', config:Config) -> int:
	if not config.silent:
		print(f"[CMD] {' '.join(command)}" )
	return subprocess.call(command)
def run_assembler(config:Config) -> None:
	if not config.run_assembler:
		return
	assert False, 'run_assembler is not implemented yet'
