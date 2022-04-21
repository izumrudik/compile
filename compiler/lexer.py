from sys import stderr
import sys

from compiler.primitives.core import DIGITS_BIN, DIGITS_HEX, DIGITS_OCTAL

from .primitives import TT, Token, DIGITS, KEYWORDS, WHITESPACE, WORD_FIRST_CHAR_ALPHABET, WORD_ALPHABET, Config, ESCAPE_TO_CHARS
from .primitives.token import draft_loc

def lex(text:str, config:Config, file_name:str) -> 'list[Token]':
	loc:draft_loc=draft_loc(file_name, text, )
	start_loc = loc
	program: 'list[Token]' = []
	while loc:
		char = loc.char
		start_loc = loc
		if char in '][}{();+%:,.$@':
			program.append(Token(start_loc.to_loc(),
			{
				'{':TT.LEFT_CURLY_BRACKET,
				'}':TT.RIGHT_CURLY_BRACKET,
				'[':TT.LEFT_SQUARE_BRACKET,
				']':TT.RIGHT_SQUARE_BRACKET,
				'(':TT.LEFT_PARENTHESIS,
				')':TT.RIGHT_PARENTHESIS,
				';':TT.SEMICOLON,
				'+':TT.PLUS,
				'%':TT.PERCENT_SIGN,
				'$':TT.DOLLAR_SIGN,
				'@':TT.AT_SIGN,
				',':TT.COMMA,
				'.':TT.DOT,
				':':TT.COLON,
			}[char]))
		elif char == '\\':#escape any char with one-char comment
			loc+=2
			continue
		elif char in WHITESPACE:
			if char == '\n':#semicolon replacement
				program.append(Token(start_loc.to_loc(), TT.NEWLINE))
			loc +=1
			continue
		elif char in DIGITS:
			loc += 1
			word = char
			digs = DIGITS
			base = 10
			if word == '0' and loc.char in 'xbo':
				word = ''
				if loc.char == 'x':#hex
					digs,base = DIGITS_HEX,16
				elif loc.char == 'b':#binary
					digs,base = DIGITS_BIN,2
				elif loc.char == 'o':#octal
					digs,base = DIGITS_OCTAL,8
				else:
					assert False, "Unreachable"
				loc+=1
			while loc.char in digs+'_':
				if loc.char != '_':
					word+=loc.char
				loc+=1
			word = str(int(word,base=base))
			if loc.char == 'c':#char
				loc+=1
				program.append(Token(start_loc.to_loc(), TT.CHARACTER, chr(int(word)) ))
				continue
			if loc.char == 's':#char
				loc+=1
				program.append(Token(start_loc.to_loc(), TT.SHORT, word))
				continue
			program.append(Token(start_loc.to_loc(), TT.INTEGER, word))
			continue
		elif char in WORD_FIRST_CHAR_ALPHABET:
			word = char
			loc+=1
			while loc.char in WORD_ALPHABET:
				word+=loc.char
				loc+=1

			program.append(Token(start_loc.to_loc(),
			TT.KEYWORD if word in KEYWORDS else TT.WORD
			, word))
			continue
		elif char in "'\"":
			loc+=1
			word = ''
			while loc.char != char:
				if loc.char == '\\':
					loc+=1
					if loc.char == 'x':#any char
						l=loc
						loc+=1
						escape = loc.char
						loc+=1
						escape += loc.char
						if escape[0] not in DIGITS_HEX or escape[1] not in DIGITS_HEX:
							print(f'ERROR: {l} expected 2 hex digits after \'\\x\' to create char with that ascii code', file=stderr)
							sys.exit(1)
						word+=chr(int(escape,16))
					word+=ESCAPE_TO_CHARS.get(loc.char, '')
					loc+=1
					continue
				word+=loc.char
				loc+=1
			loc+=1
			if loc.char == 'c':
				loc+=1
				if len(word) != 1:
					print(f"ERROR: {loc} char is not of length 1, actual length is {len(word)}", file=stderr)
					sys.exit(2)
				program.append(Token(start_loc.to_loc(), TT.CHARACTER, word))
				continue
			program.append(Token(start_loc.to_loc(), TT.STRING, word))
			continue
		elif char == '*':
			token = Token(start_loc.to_loc(), TT.ASTERISK)
			loc+=1
			program.append(token)
			continue
		elif char == '/':
			loc+=1
			if loc.char == '/':
				token = Token(start_loc.to_loc(), TT.DOUBLE_SLASH)
				loc+=1
			else:
				print(f"ERROR: {loc} division to the fraction is not supported yet", file=stderr)
				sys.exit(3)
			program.append(token)
			continue
		elif char == '=':
			token = Token(start_loc.to_loc(), TT.EQUALS_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc.to_loc(), TT.DOUBLE_EQUALS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '!':
			token = Token(start_loc.to_loc(), TT.NOT)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc.to_loc(), TT.NOT_EQUALS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '>':
			token = Token(start_loc.to_loc(), TT.GREATER_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc.to_loc(), TT.GREATER_OR_EQUAL_SIGN)
				loc+=1
			elif loc.char == '>':
				token = Token(start_loc.to_loc(), TT.DOUBLE_GREATER_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '<':
			token = Token(start_loc.to_loc(), TT.LESS_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc.to_loc(), TT.LESS_OR_EQUAL_SIGN)
				loc+=1
			if loc.char == '-':
				token = Token(start_loc.to_loc(), TT.LEFT_ARROW)
				loc+=1
			elif loc.char == '<':
				token = Token(start_loc.to_loc(), TT.DOUBLE_LESS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '-':
			token = Token(start_loc.to_loc(), TT.MINUS)
			loc+=1
			if loc.char == '>':
				loc+=1
				token = Token(start_loc.to_loc(), TT.RIGHT_ARROW)
			program.append(token)
			continue
		elif char == '#':
			while loc.char != '\n':
				loc+=1
			continue
		else:
			print(f"ERROR: {loc}: Illegal char '{char}'", file=stderr)
			sys.exit(4)
		loc+=1
	program.append(Token(start_loc.to_loc(), TT.EOF))
	return program
