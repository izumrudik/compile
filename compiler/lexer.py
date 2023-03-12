from .primitives import Place, TT, Token, ET, DIGITS_BIN, DIGITS_HEX, DIGITS_OCTAL, DIGITS, KEYWORDS, WHITESPACE, WORD_FIRST_CHAR_ALPHABET, WORD_ALPHABET, Config, ESCAPE_TO_CHARS
from .primitives.token import draft_loc
class Lexer:
	__slots__ = ('text', 'config', 'file_name', 'loc')
	def __init__(self, text:str, config:Config, file_name:str):
		self.text = text
		self.config = config
		self.file_name = file_name
		self.loc = draft_loc(file_name, text, config)
	def lex(self) -> list[Token]:
		program:list[Token] = []
		while self.loc:
			program += self.lex_token()
		program.append(Token(Place(self.loc.to_loc(),self.loc.to_loc()), TT.EOF))
		return program
	def lex_token(self) -> list[Token]:
		char = self.loc.char
		start_loc = self.loc.to_loc()
		if char in '][}{()+%:,.$@*':
			self.loc+=1
			return [Token(Place(start_loc,self.loc.to_loc()),
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
				'*':TT.ASTERISK,
			}[char])]
		elif char in WHITESPACE:
			self.loc +=1
			if char == '\n':
				return [Token(Place(start_loc,self.loc.to_loc()), TT.NEWLINE)]
			return []
		elif char in DIGITS:
			return [self.lex_digits()]
		elif char in WORD_FIRST_CHAR_ALPHABET:
			word = char
			self.loc+=1
			while self.loc.char in WORD_ALPHABET and self.loc:
				word+=self.loc.char
				self.loc+=1
			return [Token(Place(start_loc,self.loc.to_loc()),
			TT.KEYWORD if word in KEYWORDS else TT.WORD,
			word)]
		elif char in "'\"":#strings
			self.loc+=1
			word = ''
			while self.loc.char != char and self.loc:
				if self.loc.char == '\\':
					l=self.loc
					self.loc+=1
					if self.loc.char == 'x':#any char
						self.loc+=1
						escape = self.loc.char
						self.loc+=1
						escape += self.loc.char
						self.loc+=1
						if escape[0] not in DIGITS_HEX or escape[1] not in DIGITS_HEX:
							self.config.errors.add_error(ET.STR_ANY_CHAR, Place(l.to_loc(),self.loc.to_loc()), "expected 2 hex digits after \'\\x\' to create char with that ascii code")
							escape = '00'
						word+=chr(int(escape,16))
						continue
					word+=ESCAPE_TO_CHARS.get(self.loc.char, '')
					self.loc+=1
					continue
				word+=self.loc.char
				self.loc+=1
			self.loc+=1
			if self.loc.char == 'c':
				self.loc+=1
				if len(word) != 1:
					self.config.errors.add_error(ET.CHARACTER,Place(start_loc,self.loc.to_loc()),f"expected a string of length 1 because of 'c' prefix, actual length is {len(word)}")
				if len(word) < 1:
					word = chr(0)
				return [Token(Place(start_loc,self.loc.to_loc()), TT.CHAR_STR, word[0])]
			return [Token(Place(start_loc,self.loc.to_loc()), TT.STR, word)]
		elif char == '`':#template strings
			return self.lex_template_strings()
		elif char == '/':
			self.loc+=1
			if self.loc.char == '/':
				self.loc+=1
			elif self.loc.char == '*':
				previous = self.loc.char
				self.loc +=1
				while previous != '*' or self.loc.char != '/':
					previous = self.loc.char
					self.loc +=1
				self.loc += 1
				return []
			else:
				self.config.errors.add_error(ET.DIVISION, Place(start_loc,self.loc.to_loc()), "accurate division '/' is not supported yet")
			token = Token(Place(start_loc,self.loc.to_loc()), TT.DOUBLE_SLASH)
			return [token]
		elif char == '=':
			self.loc+=1
			token = Token(Place(start_loc,self.loc.to_loc()), TT.EQUALS)
			if self.loc.char == '=':
				self.loc+=1
				token = Token(Place(start_loc,self.loc.to_loc()), TT.DOUBLE_EQUALS)
			return [token]
		elif char == '!':
			self.loc+=1
			token = Token(Place(start_loc,self.loc.to_loc()), TT.NOT)
			if self.loc.char == '=':
				self.loc+=1
				token = Token(Place(start_loc,self.loc.to_loc()), TT.NOT_EQUALS)
			if self.loc.char == '<':
				self.loc+=1
				token = Token(Place(start_loc,self.loc.to_loc()), TT.FILL_GENERIC_START)
			return [token]
		elif char == '>':
			self.loc+=1
			token = Token(Place(start_loc,self.loc.to_loc()), TT.GREATER)
			if self.loc.char == '=':
				self.loc+=1
				token = Token(Place(start_loc,self.loc.to_loc()), TT.GREATER_OR_EQUAL)
			return [token]
		elif char == '<':
			self.loc+=1
			token = Token(Place(start_loc,self.loc.to_loc()), TT.LESS)
			if self.loc.char == '=':
				self.loc+=1
				token = Token(Place(start_loc,self.loc.to_loc()), TT.LESS_OR_EQUAL)
			return [token]
		elif char == '-':
			token = Token(Place(start_loc,self.loc.to_loc()), TT.MINUS)
			self.loc+=1
			if self.loc.char == '>':
				self.loc+=1
				token = Token(Place(start_loc,self.loc.to_loc()), TT.ARROW)
			return [token]
		elif char == '#':
			while self.loc.char != '\n' and self.loc:
				self.loc+=1
			return []
		else:
			self.loc+=1
			self.config.errors.add_error(ET.ILLEGAL_CHAR, Place(start_loc,self.loc.to_loc()), f"illegal character '{char}'")
			return []
		assert False, "Unreachable"
	def lex_digits(self) -> Token:
		start_loc = self.loc.to_loc()
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
		while self.loc.char in digs+'_' and self.loc:
			if self.loc.char != '_':
				word+=self.loc.char
			self.loc+=1
		if len(word) == 0:
			self.config.errors.add_error(ET.ILLEGAL_NUMBER, Place(start_loc,self.loc.to_loc()), "expected a number, but got nothing")
			word = '0'
		word = str(int(word,base=base))
		if self.loc.char == 'c':#char
			self.loc+=1
			return Token(Place(start_loc,self.loc.to_loc()), TT.CHAR_NUM, word)
		if self.loc.char == 's':#char
			self.loc+=1
			return Token(Place(start_loc,self.loc.to_loc()), TT.SHORT, word)
		return Token(Place(start_loc,self.loc.to_loc()), TT.INT, word)
	def lex_template_strings(self) -> list[Token]:
		start_loc = self.loc.to_loc()
		self.loc += 1 # `
		word = ''
		tokens:list[Token] = []
		while self.loc.char != '`' and self.loc:
			if self.loc.char == '{':
				self.loc+=1
				if self.loc.char != '{':
					tokens.append(Token(Place(start_loc,self.loc.to_loc()), TT.TEMPLATE_MIDDLE if len(tokens) != 0 else TT.TEMPLATE_HEAD, word))
					tok = self.lex_token()
					while ((tok[0].typ != TT.RIGHT_CURLY_BRACKET) if len(tok) == 1 else True) and self.loc:
						tokens+=tok
						tok = self.lex_token()
					word = ''
					start_loc = tok[0].place.start
					continue
			if self.loc.char == '}':
				l = self.loc.to_loc()
				if (self.loc+1).char != '}':
					self.config.errors.add_error(ET.TEMPLATE_DR_CURLY, Place(l,self.loc.to_loc()), "single '}' are not allowed in template strings, use '}}' instead")
				else:
					self.loc+=1
			if self.loc.char == '\\':
				if self.loc.char == '\\':
					l=self.loc.to_loc()
					self.loc+=1
					if self.loc.char == 'x':#any char
						self.loc+=1
						escape = self.loc.char
						self.loc+=1
						escape += self.loc.char
						self.loc+=1
						if escape[0] not in DIGITS_HEX or escape[1] not in DIGITS_HEX:
							self.config.errors.add_error(ET.TEMPLATE_ANY_CHAR, Place(l,self.loc.to_loc()), "expected 2 hex digits after \'\\x\' to create char with that ascii code")
							escape = '00'
						word+=chr(int(escape,16))
						continue
					word+=ESCAPE_TO_CHARS.get(self.loc.char, '')
					self.loc+=1
					continue
			word += self.loc.char
			self.loc += 1
		self.loc+=1
		tokens.append(Token(Place(start_loc,self.loc.to_loc()), TT.TEMPLATE_TAIL if len(tokens) != 0 else TT.NO_MIDDLE_TEMPLATE, word))
		return tokens

def lex(text:str, config:Config, file_name:str) -> 'list[Token]':
	return Lexer(text, config, file_name).lex()

