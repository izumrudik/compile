#!/bin/python3.10
from dataclasses import dataclass
from email.policy import default
from sys import argv, stderr

@dataclass()
class Config:
	self_name:str
	file:str|None = None

def usage(config:Config) -> str:
	return f"""Usage:
	{config.self_name} file [flags]
Flags:
	-h,--help: print this message
"""

def process_cmd_args(args:list[str]) -> Config:
	assert len(args)>0,'Error in the function above'
	self_name = args[0]
	config = Config(self_name)
	args = args[1:]
	for arg in args:
		match arg[0],arg[1],arg[2:]:
			case '-','-','help':
				print(usage(config))
				exit(0)
			case '-','-',flag:
				print(f"ERROR: flag {flag} is not supported yet",file=stderr)
				print(usage(self_name))
				exit(1)
			case '-',flag,rest:
				for subflag in flag+rest:#-smth
					match subflag:
						case 'h':
							print(usage(config))
							exit(0)
						case wildcard:
							print(f"ERROR: flag -{wildcard} is not supported yet",file=stderr)
							print(usage(config))
							exit(2)
			case file,rest1,rest2:
				if config.file is not None:
					print(f"ERROR: provided 2 files",file=stderr)
					print(usage(config))
					exit(3)
				file+=rest1+rest2
				config.file = file
	return config

def extract_file_text_from_config(config:Config) -> str:
	if config.file is None:
		print(f"ERROR: file was not provided",file=stderr)
		print(usage(config))
		exit(3)
	with open(config.file,'r') as file:
		text = file.read()
	print(text)
	return text

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
	text = extract_file_text_from_config(config)
	exit(0) 
	words = lex(text,config)
	ast = parse(words,config)
	type_check(ast,config)
	compile_to_assembly(ast,config)
	run_assembler(config)


	

if __name__ == '__main__':
	main()