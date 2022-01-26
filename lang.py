#!/bin/python3
from sys import argv


def process_cmd_args(args):
	assert False, " 'process_cmd_args' is not implemented yet"

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