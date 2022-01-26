#!/bin/python3.10
from dataclasses import dataclass
from email.policy import default
from sys import argv, stderr
from typing import Optional

@dataclass()
class Config:
	self_name:str
	file:Optional[str] = None
def usage(self_name):
	return f"""Usage:
	{self_name} file [flags]
Flags:
	Not any yet
"""

def process_cmd_args(args):
	self_name = args[0]
	config = Config(self_name)
	args = args[1:]
	for arg in args:
		match arg[0],arg[1],arg[2:]:
			case '-','-',flag:
				print(f"ERROR: flag {flag} is not supported yet",file=stderr)
				print(usage(self_name))
				exit(1)
			case '-',flag,rest:
				for subflag in flag+rest:#-smth
					match subflag:
						case wildcard:
							print(f"ERROR: flag -{wildcard} is not supported yet",file=stderr)
							print(usage(self_name))
							exit(2)	
			case file,rest1,rest2:
				if config.file is not None:
					print(f"ERROR: provided 2 files",file=stderr)
					print(usage(self_name))
					exit(3)
				file+=rest1+rest2
				config.file = file				
	print(config)
	return config

def extract_file_text_from_config(config):
	assert False, " 'extract_file_text_from_config' is not implemented yet"

def lex(text,config):
	assert False, " 'lex' is not implemented yet"

def parse(words,config):
	assert False, " 'parse' is not implemented yet"

def type_check(ast,config):
	assert False, " 'type_check' is not implemented yet"

def compile_to_assembly(ast,config):
	assert False, " 'compile_to_assembly' is not implemented yet"

def run_assembler(config):
	assert False, " 'run_assembler' is not implemented yet"




def main():
	config = process_cmd_args(argv)
	exit(0)
	text = extract_file_text_from_config(config)
	words = lex(text,config)
	ast = parse(words,config)
	type_check(ast,config)
	compile_to_assembly(ast,config)
	run_assembler(config)


	

if __name__ == '__main__':
	main()