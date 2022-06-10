from .primitives import TT, Token, ET, add_error, critical_error, DIGITS_BIN, DIGITS_HEX, DIGITS_OCTAL, DIGITS, KEYWORDS, WHITESPACE, WORD_FIRST_CHAR_ALPHABET, WORD_ALPHABET, Config, ESCAPE_TO_CHARS
from .primitives.token import draft_loc

class Lexer:
	__slots__ = ('text', 'config', 'file_name', 'loc')
	def __init__(self, text:str, config:Config, file_name:str):
		self.text = text
		self.config = config
		self.file_name = file_name
		self.loc = draft_loc(file_name, text, )
	def lex(self) -> list[Token]:
		program:list[Token] = []
		while self.loc:			
			program += self.lex_token()
		program.append(Token(self.loc.to_loc(), TT.EOF))
		return program
	def lex_token(self) -> list[Token]:
		char = self.loc.char
		start_loc = self.loc
		if char in '][}{()+%:,.$@~':
			self.loc+=1
			return [Token(start_loc.to_loc(),
			{
				'{':TT.LEFT_CURLY_BRACKET,
				'}':TT.RIGHT_CURLY_BRACKET,
				'[':TT.LEFT_SQUARE_BRACKET,
				']':TT.RIGHT_SQUARE_BRACKET,
				'(':TT.LEFT_PARENTHESIS,
				')':TT.RIGHT_PARENTHESIS,
				'+':TT.PLUS,
				'%':TT.PERCENT,
				'$':TT.DOLLAR,
				'@':TT.AT,
				',':TT.COMMA,
				'.':TT.DOT,
				':':TT.COLON,
				'~':TT.TILDE,
			}[char])]
		elif char == '\\':#escape any char with one-char comment
			self.loc+=2
			return []
		elif char in WHITESPACE:
			self.loc +=1
			if char == '\n':
				return [Token(start_loc.to_loc(), TT.NEWLINE)]
			return []
		elif char in DIGITS:
			return [self.lex_digits()]
		elif char in WORD_FIRST_CHAR_ALPHABET:
			word = char
			self.loc+=1
			while self.loc.char in WORD_ALPHABET:
				word+=self.loc.char
				self.loc+=1
			return [Token(start_loc.to_loc(),
			TT.KEYWORD if word in KEYWORDS else TT.WORD,
			word)]
		elif char in "'\"":#strings
			self.loc+=1
			word = ''
			while self.loc.char != char:
				if self.loc.char == '\\':
					self.loc+=1
					if self.loc.char == 'x':#any char
						l=self.loc
						self.loc+=1
						escape = self.loc.char
						self.loc+=1
						escape += self.loc.char
						if escape[0] not in DIGITS_HEX or escape[1] not in DIGITS_HEX:
							critical_error(ET.STR_ANY_CHAR, l.to_loc(), 'expected 2 hex digits after \'\\x\' to create char with that ascii code')
						word+=chr(int(escape,16))
					word+=ESCAPE_TO_CHARS.get(self.loc.char, '')
					self.loc+=1
					continue
				word+=self.loc.char
				self.loc+=1
			self.loc+=1
			if self.loc.char == 'c':
				self.loc+=1
				if len(word) > 1:
					add_error(ET.CHARACTER,self.loc.to_loc(),f"expected a string of length 1 because of 'c' prefix, actual length is {len(word)}")
				elif len(word) < 1:
					critical_error(ET.CHARACTER,self.loc.to_loc(),f"expected a string of length 1 because of 'c' prefix, actual length is {len(word)}")
				return [Token(start_loc.to_loc(), TT.CHARACTER, word[0])]
			return [Token(start_loc.to_loc(), TT.STRING, word)]
		elif char == '`':#template strings
			return self.lex_template_strings()
		elif char == '*':
			token = Token(start_loc.to_loc(), TT.ASTERISK)
			self.loc+=1
			return [token]
		elif char == '/':
			self.loc+=1
			if self.loc.char == '/':
				token = Token(start_loc.to_loc(), TT.DOUBLE_SLASH)
				self.loc+=1
			else:
				critical_error(ET.DIVISION, self.loc.to_loc(), "accurate division '/' is not supported yet")
			return [token]
		elif char == '=':
			token = Token(start_loc.to_loc(), TT.EQUALS)
			self.loc+=1
			if self.loc.char == '=':
				token = Token(start_loc.to_loc(), TT.DOUBLE_EQUALS)
				self.loc+=1
			return [token]
		elif char == '!':
			token = Token(start_loc.to_loc(), TT.NOT)
			self.loc+=1
			if self.loc.char == '=':
				token = Token(start_loc.to_loc(), TT.NOT_EQUALS)
				self.loc+=1
			return [token]
		elif char == '>':
			token = Token(start_loc.to_loc(), TT.GREATER)
			self.loc+=1
			if self.loc.char == '=':
				token = Token(start_loc.to_loc(), TT.GREATER_OR_EQUAL)
				self.loc+=1
			elif self.loc.char == '>':
				token = Token(start_loc.to_loc(), TT.DOUBLE_GREATER)
				self.loc+=1
			return [token]
		elif char == '<':
			token = Token(start_loc.to_loc(), TT.LESS)
			self.loc+=1
			if self.loc.char == '=':
				token = Token(start_loc.to_loc(), TT.LESS_OR_EQUAL)
				self.loc+=1
			elif self.loc.char == '<':
				token = Token(start_loc.to_loc(), TT.DOUBLE_LESS)
				self.loc+=1
			return [token]
		elif char == '-':
			token = Token(start_loc.to_loc(), TT.MINUS)
			self.loc+=1
			if self.loc.char == '>':
				self.loc+=1
				token = Token(start_loc.to_loc(), TT.ARROW)
			return [token]
		elif char == '#':
			while self.loc.char != '\n':
				self.loc+=1
			return []
		else:
			add_error(ET.ILLEGAL_CHAR, self.loc.to_loc(), f"Illegal character '{char}'")
			self.loc+=1
			return []
		assert False, "Unreachable"
	def lex_digits(self) -> Token:
		start_loc = self.loc
		char = self.loc.char
		self.loc += 1
		word = char
		digs = DIGITS
		base = 10
		if word == '0' and self.loc.char in 'xbo':
			word = ''
			if self.loc.char == 'x':#hex
				digs,base = DIGITS_HEX,16
			elif self.loc.char == 'b':#binary
				digs,base = DIGITS_BIN,2
			elif self.loc.char == 'o':#octal
				digs,base = DIGITS_OCTAL,8
			else:
				assert False, "Unreachable"
			self.loc+=1
		while self.loc.char in digs+'_':
			if self.loc.char != '_':
				word+=self.loc.char
			self.loc+=1
		word = str(int(word,base=base))
		if self.loc.char == 'c':#char
			self.loc+=1
			return Token(start_loc.to_loc(), TT.CHARACTER, chr(int(word)) )
		if self.loc.char == 's':#char
			self.loc+=1
			return Token(start_loc.to_loc(), TT.SHORT, word)
		return Token(start_loc.to_loc(), TT.INTEGER, word)
	def lex_template_strings(self) -> list[Token]:
		self.loc += 1 # `
		start_loc = self.loc
		word = ''
		tokens:list[Token] = []
		while self.loc.char != '`':
			if self.loc.char == '{':
				self.loc+=1
				if self.loc.char != '{':
					tokens.append(Token(start_loc.to_loc(), TT.TEMPLATE_MIDDLE if len(tokens) != 0 else TT.TEMPLATE_HEAD, word))
					tok = self.lex_token()
					while (tok[-1].typ != TT.RIGHT_CURLY_BRACKET) if len(tok) >= 1 else True:
						tokens+=tok
						tok = self.lex_token()
					word = ''
					start_loc = self.loc
					continue
			if self.loc.char == '}':
				self.loc+=1
				if self.loc.char != '}':
					critical_error(ET.TEMPLATE_DR_CURLY, self.loc.to_loc(), "Single '}' are not allowed in template strings, use '}}' instead")
			if self.loc.char == '\\':
				if self.loc.char == '\\':
					self.loc+=1
					if self.loc.char == 'x':#any char
						l=self.loc
						self.loc+=1
						escape = self.loc.char
						self.loc+=1
						escape += self.loc.char
						if escape[0] not in DIGITS_HEX or escape[1] not in DIGITS_HEX:
							critical_error(ET.TEMPLATE_ANY_CHAR, l.to_loc(), 'expected 2 hex digits after \'\\x\' to create char with that ascii code')
						word+=chr(int(escape,16))
					word+=ESCAPE_TO_CHARS.get(self.loc.char, '')
					self.loc+=1
					continue
			word += self.loc.char
			self.loc += 1
		self.loc+=1
		tokens.append(Token(start_loc.to_loc(), TT.TEMPLATE_TAIL if len(tokens) != 0 else TT.NO_MIDDLE_TEMPLATE, word))
		return tokens

def lex(text:str, config:Config, file_name:str) -> 'list[Token]':
	return Lexer(text, config, file_name).lex()

