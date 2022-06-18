#!/bin/env python3.10
import os
if __name__ == '__main__':
	os.environ['JARARACA_PATH'] = os.path.dirname(os.path.realpath(__file__))
	try:
		from jararaca.compiler import main
		main()
	except ModuleNotFoundError:
		exec("""\
from compiler import main
main()\
""") #'type: ignore' does not help
# mypy thinks that since this folder has __init__.py, it will always be a module (jararaca)
# but when running this script (__name__ == '__main__') that is not what actually happening