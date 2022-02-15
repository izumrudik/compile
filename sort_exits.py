#!/bin/python
"""
sort exits by order
"""
import re
with open('lang.py', encoding='UTF-8') as file:
	text = file.read()

RARE_CHAR = chr(2**10+15*31)

def slices(txt:str) -> tuple[int,int]:
	"""
Get slices
	"""
	group = re.search(r'exit\(([1-9][0-9]*)\)',txt)
	if group is None:
		exit(1)
	return group.start(),group.end()
length = len(re.findall(r'exit\(([1-9][0-9]*)\)',text))
for i in range(1,length+1):
	s,e = slices(text)
	text = text[:s]+f'exit({i}{RARE_CHAR})'+text[e:]
with open('lang.py','w', encoding='UTF-8') as file:
	file.write(text.replace(RARE_CHAR,''))
