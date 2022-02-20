from sys import stderr
import sys
from .primitives import TT, Token, Loc, DIGITS, KEYWORDS, WHITESPACE, WORD_ALPHABET, Config, escape_to_chars

def lex(text:str, config:Config) -> 'list[Token]':
	loc=Loc(config.file, text, )
	start_loc = loc
	program: list[Token] = []
	while loc:
		char = loc.char
		start_loc = loc
		if char in '}{();+%:,':
			program.append(Token(start_loc,
			{
				'{':TT.LEFT_CURLY_BRACKET,
				'}':TT.RIGHT_CURLY_BRACKET,
				'(':TT.LEFT_PARENTHESIS,
				')':TT.RIGHT_PARENTHESIS,
				';':TT.SEMICOLON,
				'+':TT.PLUS,
				'%':TT.PERCENT_SIGN,
				',':TT.COMMA,
				':':TT.COLON,
			}[char]))
		elif char == '\\':#escape any char with one-char comment
			loc+=2
			continue
		elif char in WHITESPACE:
			if char == '\n':#semicolon replacement
				program.append(Token(start_loc, TT.NEWLINE))
			loc+=1
			continue
		elif char in DIGITS:# important, that it is before word lexing
			word = char
			loc += 1
			while loc.char in DIGITS:
				word+=loc.char
				loc+=1
			program.append(Token(start_loc, TT.DIGIT, word))
			continue
		elif char in WORD_ALPHABET:
			word = char
			loc+=1
			while loc.char in WORD_ALPHABET:
				word+=loc.char
				loc+=1

			program.append(Token(start_loc,
			TT.KEYWORD if word in KEYWORDS else TT.WORD
			, word))
			continue
		elif char in "'\"":
			loc+=1
			word = ''
			while loc.char != char:
				if loc.char == '\\':
					loc+=1
					word+=escape_to_chars.get(loc.char, loc.char)
					loc+=1
					continue
				word+=loc.char
				loc+=1
			program.append(Token(start_loc, TT.STRING, word))
		elif char == '*':
			token = Token(start_loc, TT.ASTERISK)
			loc+=1
			#if loc.char == '*':
			#	loc+=1
			#	token = Token(start_loc, TT.double_asterisk)
			program.append(token)
			continue
		elif char == '/':
			token = Token(start_loc, TT.SLASH)
			loc+=1
			if loc.char == '/':
				token = Token(start_loc, TT.DOUBLE_SLASH)
				loc+=1
			else:
				print(f"ERROR: {loc} division to the fraction is not supported yet", file=stderr)
				sys.exit(7)
			program.append(token)
			continue
		elif char == '=':
			token = Token(start_loc, TT.EQUALS_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.DOUBLE_EQUALS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '!':
			token = Token(start_loc, TT.NOT)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.NOT_EQUALS_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '>':
			token = Token(start_loc, TT.GREATER_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.GREATER_OR_EQUAL_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '<':
			token = Token(start_loc, TT.LESS_SIGN)
			loc+=1
			if loc.char == '=':
				token = Token(start_loc, TT.LESS_OR_EQUAL_SIGN)
				loc+=1
			program.append(token)
			continue
		elif char == '-':
			token = Token(start_loc, TT.MINUS)
			loc+=1
			if loc.char == '>':
				loc+=1
				token = Token(start_loc, TT.ARROW)
			program.append(token)
			continue
		elif char == '#':
			while loc.char != '\n':
				loc+=1
			continue
		else:
			print(f"ERROR: {loc}: Illegal char '{char}'", file=stderr)
			sys.exit(8)
		loc+=1
	program.append(Token(start_loc, TT.EOF))
	return program
