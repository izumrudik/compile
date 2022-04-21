#!/bin/env python3.10
if __name__ == '__main__':
	import os
	os.environ['JARARACA_PATH'] = os.path.dirname(os.path.realpath(__file__))
	from compiler import main
	main()
