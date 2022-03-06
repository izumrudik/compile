from sys import stderr
import sys
from typing import Callable

from .primitives import nodes, Node, TT, Token, Config, Type, Ptr, INT, BOOL, STR, VOID, PTR, StructType
from .utils import extract_ast_from_file_name

class Parser:
	__slots__ = ('words', 'config', 'idx', 'parsed_tops')
	def __init__(self, words:'list[Token]', config:Config) -> None:
		self.words      :'list[Token]' = words
		self.config     :Config        = config
		self.idx        :int           = 0
		self.parsed_tops:'list[Node]'  = []
	def adv(self) -> Token:
		"""advance current word, and return what was current"""
		ret = self.current
		self.idx+=1
		while self.current == TT.NEWLINE:
			self.idx+=1
		return ret
	@property
	def current(self) -> Token:
		return self.words[self.idx]
	def parse(self) -> nodes.Tops:
		while self.current == TT.NEWLINE:
			self.adv() # skip newlines
		while self.current.typ != TT.EOF:
			top = self.parse_top()
			if top is not None:
				self.parsed_tops.append(top)
			while self.current == TT.NEWLINE:
				self.adv() # skip newlines
		return nodes.Tops(self.parsed_tops)
	def parse_top(self) -> 'Node|None':
		if self.current.equals(TT.KEYWORD, 'fun'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of function after keyword 'fun'", file=stderr)
				sys.exit(3)
			name = self.adv()

			#parse contract of the fun
			input_types:list[nodes.TypedVariable] = []
			while self.next is not None:
				if self.next.typ != TT.COLON:
					break
				input_types.append(self.parse_typed_variable())

			output_type:Type = VOID
			if self.current.typ == TT.ARROW: # provided any output types
				self.adv()
				output_type = self.parse_type()

			code = self.parse_code_block()
			return nodes.Fun(name, input_types, output_type, code)
	
		elif self.current.equals(TT.KEYWORD, 'memo'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of memory region after keyword 'memo'", file=stderr)
				sys.exit(4)
			name = self.adv()
			size = self.parse_CTE()
			return nodes.Memo(name, size)
		elif self.current.equals(TT.KEYWORD, 'var'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of var-memory region after keyword 'var'", file=stderr)
				sys.exit(5)
			name = self.adv()
			typ = self.parse_type()
			return nodes.Var(name, typ)
		elif self.current.equals(TT.KEYWORD, 'const'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of constant after keyword 'const'", file=stderr)
				sys.exit(6)
			name = self.adv()
			value = self.parse_CTE()
			return nodes.Const(name, value)

		elif self.current.equals(TT.KEYWORD, 'include'):
			self.adv()
			if self.current.typ != TT.STRING:
				print(f"ERROR: {self.current.loc}: expected file path after keyword 'include'", file=stderr)
				sys.exit(7)
			path = self.adv().operand
			tops = extract_ast_from_file_name(path, self.config)[1].tops
			self.parsed_tops.extend(tops)
			return None
		elif self.current.equals(TT.KEYWORD, 'struct'):
			loc = self.adv().loc
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc}: expected name of structure after keyword 'struct'", file=stderr)
				sys.exit(8)
			name = self.adv()
			if self.current.typ != TT.LEFT_CURLY_BRACKET:
				print(f"ERROR: {self.current.loc}: expected struct block starting with '{{' ", file=stderr)
				sys.exit(9)
			self.adv()
			variables=[]
			while self.current == TT.SEMICOLON:
				self.adv()
			while self.current != TT.RIGHT_CURLY_BRACKET:
				var = self.parse_struct_statement()
				variables.append(var)
				if self.current == TT.RIGHT_CURLY_BRACKET:
					break
				if self.words[self.idx-1] != TT.NEWLINE:#there was at least 1 self.adv() (for '{'), so we safe 
					if self.current != TT.SEMICOLON:
						print(f"ERROR: {self.current.loc}: expected newline, ';' or '}}' ", file=stderr)
						sys.exit(10)
				while self.current == TT.SEMICOLON:
					self.adv()
			self.adv()
			return nodes.Struct(loc,name, variables)
		else:
			print(f"ERROR: {self.current.loc}: unrecognized top-level structure while parsing", file=stderr)
			sys.exit(11)
	def parse_struct_statement(self) -> 'nodes.TypedVariable':
		if self.next is not None:
			if self.next == TT.COLON:
				return self.parse_typed_variable()
		print(f"ERROR: {self.current.loc}: unrecognized struct statement",file=stderr)
		sys.exit(12)
	def parse_CTE(self) -> int:
		def parse_term_int_CTE() -> int:
			if self.current == TT.DIGIT:
				return int(self.adv().operand)
			if self.current == TT.WORD:
				for top in self.parsed_tops:
					if isinstance(top, nodes.Const):
						if top.name == self.current:
							self.adv()
							return top.value
			print(f"ERROR: {self.current.loc}: '{self.current}' is not supported in compile-time-evaluation", file=stderr)
			sys.exit(13)
			
			

		operations = (
			TT.PLUS,
			TT.MINUS,

			TT.ASTERISK,
			TT.SLASH,

			TT.DOUBLE_ASTERISK,
			TT.DOUBLE_SLASH,
			TT.PERCENT_SIGN,
		)
		left:int = parse_term_int_CTE()
		while self.current.typ in operations:
			op_token = self.adv()
			right = parse_term_int_CTE()
			if   op_token == TT.PLUS        : left = left +  right
			elif op_token == TT.MINUS       : left = left -  right
			elif op_token == TT.ASTERISK    : left = left *  right
			elif op_token == TT.DOUBLE_SLASH: left = left // right
			elif op_token == TT.PERCENT_SIGN: left = left %  right
			else:
				print(f"ERROR: {self.current.loc}: unknown operation {op_token} in compile time evaluation", file=stderr)
		return left
	def parse_code_block(self) -> nodes.Code:
		if self.current.typ != TT.LEFT_CURLY_BRACKET:
			print(f"ERROR: {self.current.loc}: expected code block starting with '{{' ", file=stderr)
			sys.exit(14)
		self.adv()
		code=[]
		while self.current == TT.SEMICOLON:
			self.adv()
		while self.current != TT.RIGHT_CURLY_BRACKET:
			statement = self.parse_statement()
			code.append(statement)
			if self.current == TT.RIGHT_CURLY_BRACKET:
				break
			if self.words[self.idx-1] != TT.NEWLINE:#there was at least 1 self.adv() (for '{'), so we safe 
				if self.current != TT.SEMICOLON:
					print(f"ERROR: {self.current.loc}: expected newline, ';' or '}}' ", file=stderr)
					sys.exit(15)
			while self.current == TT.SEMICOLON:
				self.adv()
		self.adv()
		return nodes.Code(code)

	@property
	def next(self) -> 'Token | None':
		if len(self.words)>self.idx+1:
			return self.words[self.idx+1]
		return None
	def parse_statement(self) -> 'Node|Token':
		if self.next is not None:#variables
			if self.next == TT.COLON:
				var = self.parse_typed_variable()
				if self.current.typ != TT.EQUALS_SIGN:#var:type
					return nodes.Defining(var)
				#var:type = value
				self.adv()
				value = self.parse_expression()
				return nodes.Assignment(var, value)
			elif self.next == TT.EQUALS_SIGN:#var = value
				if self.current != TT.WORD:
					print(f"ERROR: {self.current.loc} expected variable name before equals sign",file=stderr)
					sys.exit(16)
				name = self.adv()
				self.adv()#skip equals sign
				value = self.parse_expression()
				return nodes.ReAssignment(name, value)
		if self.current.equals(TT.KEYWORD, 'if'):
			return self.parse_if()
		if self.current.equals(TT.KEYWORD, 'while'):
			return self.parse_while()
		elif self.current.equals(TT.KEYWORD, 'return'):
			loc = self.adv().loc
			return nodes.Return(loc,self.parse_expression())
		return nodes.ExprStatement(self.parse_expression())
	def parse_if(self) -> Node:
		loc = self.adv().loc
		condition = self.parse_expression()
		if_code = self.parse_code_block()
		if self.current.equals(TT.KEYWORD, 'elif'):
			else_block = self.parse_if()
			return nodes.If(loc, condition, if_code, else_block)
		if self.current.equals(TT.KEYWORD, 'else'):
			self.adv()
			else_code = self.parse_code_block()
			return nodes.If(loc, condition, if_code, else_code)
		return nodes.If(loc, condition, if_code)
	def parse_while(self) -> Node:
		loc = self.adv().loc
		condition = self.parse_expression()
		code = self.parse_code_block()
		return nodes.While(loc, condition, code)
	def parse_typed_variable(self) -> nodes.TypedVariable:
		if self.current != TT.WORD:
			print(f"ERROR: {self.current.loc} expected variable name before colon",file=stderr)
			sys.exit(17)
		name = self.adv()
		assert self.current.typ == TT.COLON, "bug in function above ^, or in this one"
		self.adv()#type
		typ = self.parse_type()

		return nodes.TypedVariable(name, typ)
	def parse_type(self) -> Type:
		const = {
			'void': VOID,
			'str' : STR,
			'int' : INT,
			'bool': BOOL,
			'ptr' : PTR,
		}
		out:'Type|None' = const.get(self.current.operand) # for now that is enough
		if out is None:
			for top in self.parsed_tops:
				if isinstance(top,nodes.Struct):
					a = top.name.operand
					if self.current.operand == a:
						out = StructType(top)
					break
			else:
				print(f"ERROR: {self.current.loc}: Unrecognized type {self.current}", file=stderr)
				sys.exit(18)
		self.adv()
		if out is PTR and self.current==TT.LEFT_PARENTHESIS:
			self.adv()
			out = Ptr(self.parse_type())
		
			if self.current != TT.RIGHT_PARENTHESIS:
				print(f"ERROR: {self.current.loc}: expected ')', '(' was opened and never closed", file=stderr)
				sys.exit(19)
			self.adv()
		return out
	def parse_expression(self) -> 'Node | Token':
		return self.parse_exp0()
	def bin_exp_parse_helper(
		self,
		next_exp:'Callable[[], Node|Token]',
		operations:'list[TT]'
	) -> 'Node | Token':
		left = next_exp()
		while self.current.typ in operations:
			op_token = self.adv()
			right = next_exp()
			left = nodes.BinaryExpression(left, op_token, right)
		return left

	def parse_exp0(self) -> 'Node | Token':
		self_exp = self.parse_exp0
		next_exp = self.parse_exp1
		operations = (
			TT.NOT,
		)
		if self.current.typ in operations:
			op_token = self.adv()
			right = self_exp()
			return nodes.UnaryExpression(op_token, right)
		return next_exp()

	def parse_exp1(self) -> 'Node | Token':
		next_exp = self.parse_exp2
		return self.bin_exp_parse_helper(next_exp, [
			TT.LESS_SIGN,
			TT.GREATER_SIGN,
			TT.DOUBLE_EQUALS_SIGN,
			TT.NOT_EQUALS_SIGN,
			TT.LESS_OR_EQUAL_SIGN,
			TT.GREATER_OR_EQUAL_SIGN,
		])

	def parse_exp2(self) -> 'Node | Token':
		next_exp = self.parse_exp3
		return self.bin_exp_parse_helper(next_exp, [
			TT.PLUS,
			TT.MINUS,
		])
	def parse_exp3(self) -> 'Node | Token':
		next_exp = self.parse_exp4
		return self.bin_exp_parse_helper(next_exp, [
			TT.ASTERISK,
			TT.SLASH,
		])
	def parse_exp4(self) -> 'Node | Token':
		next_exp = self.parse_exp5
		return self.bin_exp_parse_helper(next_exp, [
			TT.DOUBLE_ASTERISK,
			TT.DOUBLE_SLASH,
			TT.DOUBLE_GREATER_SIGN,
			TT.DOUBLE_LESS_SIGN,
			TT.PERCENT_SIGN,
		])
	def parse_exp5(self) -> 'Node | Token':
		next_exp = self.parse_term
		operations = [
			'or',
			'xor',
			'and',
		]
		left = next_exp()
		while self.current == TT.KEYWORD and self.current.operand in operations:
			op_token = self.adv()
			right = next_exp()
			left = nodes.BinaryExpression(left, op_token, right)
		return left

	def parse_term(self) -> 'Node | Token':
		if self.current.typ in (TT.DIGIT, TT.STRING):
			token = self.adv()
			return token
		if self.current.typ == TT.LEFT_PARENTHESIS:
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:
				print(f"ERROR: {self.current.loc}: expected ')'", file=stderr)
				sys.exit(20)
			self.adv()
			return expr
		if self.current == TT.WORD: #trying to extract function call
			name = self.adv()
			if self.current == TT.LEFT_PARENTHESIS:
				self.adv()
				args = []
				while self.current.typ != TT.RIGHT_PARENTHESIS:
					args.append(self.parse_expression())
					if self.current.typ == TT.RIGHT_PARENTHESIS:
						break
					if self.current.typ != TT.COMMA:
						print(f"ERROR: {self.current.loc}: expected ', ' or ')' ", file=stderr)
						sys.exit(21)
					self.adv()
				self.adv()
				return nodes.FunctionCall(name, args)
			elif self.current == TT.DOT:
				dot = self.adv().loc
				if self.current != TT.WORD:
					print(f"ERROR: {self.current.loc}: expected word after '.'",file=stderr)
					sys.exit(22)
				ref = self.adv()
				return nodes.Dot(nodes.ReferTo(name), ref,dot)
			return nodes.ReferTo(name)
		elif self.current == TT.KEYWORD: # intrinsic singletons constants
			name = self.adv()
			return nodes.IntrinsicConstant(name)
		else:
			print(f"ERROR: {self.current.loc}: Unexpected token while parsing term", file=stderr)
			sys.exit(23)