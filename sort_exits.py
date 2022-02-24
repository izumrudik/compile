#!/bin/python
"""
sort exits by order
"""
import re
idx = 1
def correct(file_name:str) -> None:
	global idx
	with open(file_name, encoding='UTF-8') as file:
		text = file.read()

	RARE_CHAR = chr(2**10+15*31)

	def slices(txt:str) -> tuple[int, int]:
		"""
	Get slices
		"""
		group = re.search(r'exit\(([1-9][0-9]*)\)', txt)
		if group is None:
			exit(1)
		return group.start(), group.end()
	length = len(re.findall(r'exit\(([1-9][0-9]*)\)', text)) + idx
	while idx<length:
		s, e = slices(text)
		text = text[:s]+f'exit({idx}{RARE_CHAR})'+text[e:]
		idx+=1
	with open(file_name, 'w', encoding='UTF-8') as file:
		file.write(text.replace(RARE_CHAR, ''))



correct('./lang.py')
correct('./compiler/__init__.py')
correct('./compiler/generator.py')
correct('./compiler/lexer.py')
correct('./compiler/parser.py')
correct('./compiler/type_checker.py')
correct('./compiler/utils.py')
correct('./compiler/primitives/__init__.py')
correct('./compiler/primitives/core.py')
correct('./compiler/primitives/nodes.py')
correct('./compiler/primitives/run.py')
correct('./compiler/primitives/token.py')
correct('./compiler/primitives/type.py')
