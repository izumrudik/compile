import os
from sys import stderr
import sys
from typing import Callable, NoReturn, TypeVar

from .primitives import nodes, Node, TT, Token, Config, Type, types, JARARACA_PATH
from .utils import extract_module_from_file_name

class Parser:
	__slots__ = ('words', 'config', 'idx', 'parsed_tops', 'module_name', 'module_path')
	def __init__(self, words:'list[Token]', config:Config, module_name:str, module_path:str) -> None:
		self.words      :'list[Token]' = words
		self.config     :Config        = config
		self.idx        :int           = 0
		self.parsed_tops:'list[Node]'  = []
		self.module_name:str           = module_name
		self.module_path:str           = module_path
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
	def parse(self) -> nodes.Module:
		
		#first, include std.builtin's if I am not std.builtin
		if self.module_path != 'std.builtin':
			builtins = extract_module_from_file_name(os.path.join(JARARACA_PATH,'std','builtin.ja'),self.config,'<built-in>','std.builtin')
			import_names = []
			for top in builtins.tops:
				if isinstance(top,nodes.Fun|nodes.Mix|nodes.Const|nodes.Use):
					import_names.append(top.name)
			self.parsed_tops.append(nodes.FromImport('std.builtin', '<built-in>', builtins, import_names))

		while self.current == TT.NEWLINE:
			self.adv() # skip newlines
		while self.current.typ != TT.EOF:
			top = self.parse_top()
			if top is not None:
				self.parsed_tops.append(top)
			while self.current == TT.NEWLINE:
				self.adv() # skip newlines
		return nodes.Module(self.parsed_tops,self.module_name,self.module_path)
	def parse_top(self) -> 'Node|None':
		if self.current.equals(TT.KEYWORD, 'fun'):
			return self.parse_fun()
		elif self.current.equals(TT.KEYWORD, 'use'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc} expected name of function to use from outside", file=stderr)
				sys.exit(5)
			name = self.adv()
			#name(type, type) -> type
			if self.current.typ != TT.LEFT_PARENTHESIS:
				print(f"ERROR: {self.current.loc} expected '(' after 'use' and function name", file=stderr)
				sys.exit(6)
			self.adv()
			input_types:list[Type] = []
			while self.current != TT.RIGHT_PARENTHESIS:
				input_types.append(self.parse_type())
				if self.current == TT.RIGHT_PARENTHESIS:
					break
				if self.current != TT.COMMA:
					print(f"ERROR: {self.current.loc} expected ',' or ')' ", file=stderr)
					sys.exit(7)
				self.adv()
			self.adv()
			output_type:Type = types.VOID
			if self.current.typ == TT.RIGHT_ARROW: # provided any output types
				self.adv()
				output_type = self.parse_type()
			return nodes.Use(name, input_types, output_type)
		elif self.current.equals(TT.KEYWORD, 'var'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc} expected name of var-memory region after keyword 'var'", file=stderr)
				sys.exit(8)
			name = self.adv()
			typ = self.parse_type()
			return nodes.Var(name, typ)
		elif self.current.equals(TT.KEYWORD, 'const'):
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc} expected name of constant after keyword 'const'", file=stderr)
				sys.exit(9)
			name = self.adv()
			value = self.parse_CTE()
			return nodes.Const(name, value)
		elif self.current.equals(TT.KEYWORD, 'import'):
			self.adv()
			path,nam,module = self.parse_module_path()
			return nodes.Import(path,nam,module)
		elif self.current.equals(TT.KEYWORD, 'from'):
			self.adv()
			path,nam,module = self.parse_module_path()
			if not self.current.equals(TT.KEYWORD, 'import'):
				print(f"ERROR: {self.current.loc} expected keyword 'import' after path in 'from ... import ...' top", file=stderr)
				sys.exit(11)
			self.adv()
			if self.current != TT.WORD:
				print(f"ERROR: {self.current.loc} expected word, to import after keyword 'import' in 'from ... import ...' top", file=stderr)
				sys.exit(11)
			names = [self.adv()]
			while self.current == TT.COMMA:
				self.adv()
				if self.current != TT.WORD:
					print(f"ERROR: {self.current.loc} expected word, to import after comma in 'from ... import ...' top", file=stderr)
					sys.exit(11)
				names.append(self.adv())
				
			return nodes.FromImport(path,nam,module,names)

		elif self.current.equals(TT.KEYWORD, 'struct'):
			loc = self.adv().loc
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc} expected name of structure after keyword 'struct'", file=stderr)
				sys.exit(11)
			name = self.adv()
			if self.current.typ != TT.LEFT_CURLY_BRACKET:
				print(f"ERROR: {self.current.loc} expected structure block starting with '{{' ", file=stderr)
				sys.exit(12)
			self.adv()
			variables:list[nodes.TypedVariable] = []
			struct:'None|nodes.Struct' = None
			while self.current == TT.SEMICOLON:
				self.adv()
			while self.current != TT.RIGHT_CURLY_BRACKET:
				if self.current.equals(TT.KEYWORD, 'fun'):
					struct = nodes.Struct(loc, name, variables)
					self.parsed_tops.append(struct)
				if struct is None:
					variables.append(self.parse_struct_statement())
				else:
					if not self.current.equals(TT.KEYWORD, 'fun'):
						print(f"ERROR: {self.current.loc} expected structure's function declaration to be after structure statements (expected 'fun' keyword)", file=stderr)
						sys.exit(13)
					self.parsed_tops.append(self.parse_fun(struct))
				if self.current == TT.RIGHT_CURLY_BRACKET:
					break
				if self.words[self.idx-1] != TT.NEWLINE:#there was at least 1 self.adv() (for '{'), so we safe
					if self.current != TT.SEMICOLON:
						print(f"ERROR: {self.current.loc} expected newline, ';' or '}}' ", file=stderr)
						sys.exit(14)
				while self.current == TT.SEMICOLON:
					self.adv()
			self.adv()
			if struct is None:
				return nodes.Struct(loc, name, variables)
			return None

		elif self.current.equals(TT.KEYWORD, 'mix'):
			loc = self.adv().loc
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc} expected name of mix after keyword 'mix'", file=stderr)
				sys.exit(15)
			name = self.adv()
			funs = self.block_parse_helper(self.parse_mix_statement)
			return nodes.Mix(loc,name,funs)

		else:
			print(f"ERROR: {self.current.loc} unrecognized top-level structure while parsing", file=stderr)
			sys.exit(20)
	def parse_mix_statement(self) -> 'Token':
		if self.current != TT.WORD:
			print(f"ERROR: {self.current.loc} expected word as a name of function while parsing mix", file=stderr)
			sys.exit(21)
		return self.adv()
	def parse_module_path(self) -> 'tuple[str,str,nodes.Module]':
		if self.current.typ != TT.WORD:
			print(f"ERROR: {self.current.loc} expected name of module after keyword 'import'", file=stderr)
			sys.exit(10)
		next_level = self.adv().operand
		path:str = next_level
		link_path = os.path.join(JARARACA_PATH,'packets',next_level+'.link')
		if not os.path.exists(link_path):
			print(f"ERROR: {self.current.loc} module '{path}' not found in at '{link_path}'", file=stderr)
			sys.exit(11)
		with open(link_path,'r') as f:
			file_path = f.read()

		while self.current == TT.DOT:
			self.adv()
			if self.current.typ != TT.WORD:
				print(f"ERROR: {self.current.loc} expected name of next module in the hierarchy after dot", file=stderr)
				sys.exit(10)
			if not os.path.isdir(file_path):
				print(f"ERROR: {self.current.loc} module '{path}' not found in at '{file_path}'", file=stderr)
				sys.exit(11)
			next_level = self.adv().operand
			path += '.' + next_level
			file_path = os.path.join(file_path,next_level)
		if not os.path.isdir(file_path):
			file_path += '.ja'
		else:
			file_path = os.path.join(file_path,'__init__.ja')
		if not os.path.exists(file_path):
			print(f"ERROR: {self.current.loc} module '{path}' not found in at '{file_path}'", file=stderr)
			sys.exit(11)
		try:
			module = extract_module_from_file_name(file_path,self.config,next_level,path)
		except RecursionError:
			print(f"ERROR: {self.current.loc} recursion depth exceeded", file=stderr)
			sys.exit(1)	
		return path,next_level,module
	def parse_fun(self,bound:'None|nodes.Struct' = None) -> nodes.Fun:
		self.adv()
		if self.current.typ != TT.WORD:
			print(f"ERROR: {self.current.loc} expected name of function after keyword 'fun'", file=stderr)
			sys.exit(22)
		name = self.adv()

		#parse contract of the fun
		input_types:list[nodes.TypedVariable] = []
		while self.next is not None:
			if self.next.typ != TT.COLON:
				break
			input_types.append(self.parse_typed_variable())

		output_type:Type = types.VOID
		if self.current.typ == TT.RIGHT_ARROW: # provided any output types
			self.adv()
			output_type = self.parse_type()

		code = self.parse_code_block()
		return nodes.Fun(name, input_types, output_type, code, bound)

	def parse_struct_statement(self) -> 'nodes.TypedVariable':
		if self.next is not None:
			if self.next == TT.COLON:
				return self.parse_typed_variable()
		print(f"ERROR: {self.current.loc} unrecognized struct statement", file=stderr)
		sys.exit(23)
	def parse_CTE(self) -> int:
		def parse_term_int_CTE() -> int:
			if self.current == TT.INTEGER:
				return int(self.adv().operand)
			if self.current == TT.WORD:
				def find_a_const(tops:list[Node]) -> int|None:
					for top in tops:
						if isinstance(top, nodes.Const):
							if top.name == self.current:
								self.adv()
								return top.value
						if isinstance(top, nodes.FromImport):
							for name in top.imported_names:
								if name == self.current:
									return find_a_const(top.module.tops)
					return None
				i = find_a_const(self.parsed_tops)
				if i is not None: return i
			print(f"ERROR: {self.current.loc} term '{self.current}' is not supported in compile-time-evaluation", file=stderr)
			sys.exit(24)



		operations = (
			TT.PLUS,
			TT.MINUS,

			TT.ASTERISK,

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
				print(f"ERROR: {self.current.loc} unknown operation {op_token} in compile time evaluation", file=stderr)
		return left
	def parse_code_block(self) -> nodes.Code:
		return nodes.Code(self.block_parse_helper(self.parse_statement))
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
					print(f"ERROR: {self.current.loc} expected variable name before equals sign", file=stderr)
					sys.exit(25)
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
		expr = self.parse_expression()
		if self.current == TT.LEFT_ARROW:
			loc = self.adv().loc
			return nodes.Save(expr, self.parse_expression(),loc)
		return nodes.ExprStatement(expr)
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
			print(f"ERROR: {self.current.loc} expected variable name before colon", file=stderr)
			sys.exit(26)
		name = self.adv()
		assert self.current.typ == TT.COLON, "bug in function above ^, or in this one"
		self.adv()#type
		typ = self.parse_type()

		return nodes.TypedVariable(name, typ)
	def parse_type(self) -> Type:
		if self.current == TT.WORD:
			const = {
				'void' : types.VOID,
				'bool' : types.BOOL,
				'char' : types.CHAR,
				'short': types.SHORT,
				'str'  : types.STR,
				'int'  : types.INT,
			}
			out:'Type|None' = const.get(self.current.operand) # for now that is enough
			
			if out is None and self.current.operand == 'ptr' and self.next == TT.LEFT_PARENTHESIS:
				self.adv()
				self.adv()
				out = types.Ptr(self.parse_type())
				if self.current != TT.RIGHT_PARENTHESIS:
					print(f"ERROR: {self.current.loc} expected ')', '(' was opened and never closed", file=stderr)
					sys.exit(27)
				self.adv()
				return out
			if out is None:
				def find_a_struct(tops:'list[Node]') -> 'types.Struct|None':
					for top in tops:
						if isinstance(top,nodes.Struct):
							a = top.name.operand
							if self.current.operand == a:
								self.adv()
								return types.Struct(top)
						if isinstance(top, nodes.FromImport):
							for name in top.imported_names:
								if name == self.current:
									return find_a_struct(top.module.tops)
					return None
				i = find_a_struct(self.parsed_tops)
				if i is not None: return i
				print(f"ERROR: {self.current.loc} Unrecognized type {self.current.operand}", file=stderr)
				sys.exit(28)
			self.adv()
			return out
		elif self.current == TT.LEFT_SQUARE_BRACKET:#array
			self.adv()
			if self.current == TT.RIGHT_SQUARE_BRACKET:
				size = 0
			else:
				size = self.parse_CTE()
			if self.current != TT.RIGHT_SQUARE_BRACKET:
				print(f"ERROR: {self.current.loc} expected ']', '[' was opened and never closed", file=stderr)
				sys.exit(29)
			self.adv()
			typ = self.parse_type()
			return types.Array(size,typ)

		else:
			print(f"ERROR: {self.current.loc} Unrecognized type", file=stderr)
			sys.exit(30)			

	def parse_expression(self) -> 'Node | Token':
		return self.parse_exp0()
	T = TypeVar('T')
	def block_parse_helper(
		self,
		parse_statement:'Callable[[], T]'
			) -> 'list[T]':
		if self.current.typ != TT.LEFT_CURLY_BRACKET:
			print(f"ERROR: {self.current.loc} expected block starting with '{{' ", file=stderr)
			sys.exit(31)
		self.adv()
		statements = []
		while self.current == TT.SEMICOLON:
			self.adv()
		while self.current != TT.RIGHT_CURLY_BRACKET:
			statement = parse_statement()
			statements.append(statement)
			if self.current == TT.RIGHT_CURLY_BRACKET:
				break
			if self.words[self.idx-1] != TT.NEWLINE:#there was at least 1 self.adv() (for '{'), so we safe
				if self.current != TT.SEMICOLON:
					print(f"ERROR: {self.current.loc} expected newline, ';' or '}}' ", file=stderr)
					sys.exit(32)
			while self.current == TT.SEMICOLON:
				self.adv()
		self.adv()
		return statements
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
		next_exp = self.parse_exp1
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
		])
	def parse_exp4(self) -> 'Node | Token':
		next_exp = self.parse_exp5
		return self.bin_exp_parse_helper(next_exp, [
			TT.DOUBLE_SLASH,
			TT.DOUBLE_GREATER_SIGN,
			TT.DOUBLE_LESS_SIGN,
			TT.PERCENT_SIGN,
		])
	def parse_exp5(self) -> 'Node | Token':
		self_exp = self.parse_exp5
		next_exp = self.parse_exp6
		operations = (
			TT.NOT,
			TT.AT_SIGN,
		)
		if self.current.typ in operations:
			op_token = self.adv()
			right = self_exp()
			return nodes.UnaryExpression(op_token, right)
		return next_exp()

	def parse_exp6(self) -> 'Node | Token':
		next_exp = self.parse_term
		left = next_exp()
		while self.current.typ in (TT.DOT,TT.LEFT_SQUARE_BRACKET):
			if self.current == TT.DOT:
				loc = self.adv().loc
				if self.current != TT.WORD:
					print(f"ERROR: {self.current.loc} expected word after '.'", file=stderr)
					sys.exit(33)
				access = self.adv()
				if self.current == TT.LEFT_PARENTHESIS:
					self.adv()
					args = []
					while self.current.typ != TT.RIGHT_PARENTHESIS:
						args.append(self.parse_expression())
						if self.current.typ == TT.RIGHT_PARENTHESIS:
							break
						if self.current.typ != TT.COMMA:
							print(f"ERROR: {self.current.loc} expected ', ' or ')' ", file=stderr)
							sys.exit(34)
						self.adv()
					self.adv()
					left = nodes.DotCall(left, nodes.FunctionCall(access, args), loc)
				else:
					left = nodes.Dot(left, access,loc)
			elif self.current == TT.LEFT_SQUARE_BRACKET:
				loc = self.adv().loc
				idx = self.parse_expression()
				if self.current != TT.RIGHT_SQUARE_BRACKET:
					print(f"ERROR: {self.current.loc} expected ']', '[' was opened and never closed", file=stderr)
					sys.exit(35)
				self.adv()
				left = nodes.GetItem(left, idx, loc)
		return left
	def parse_term(self) -> 'Node | Token':
		if self.current.typ in (TT.INTEGER, TT.STRING, TT.CHARACTER, TT.SHORT):
			token = self.adv()
			return token
		elif self.current.typ == TT.LEFT_PARENTHESIS:
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:
				print(f"ERROR: {self.current.loc} expected ')'", file=stderr)
				sys.exit(36)
			self.adv()
			return expr
		elif self.current == TT.WORD: #name or func()
			name = self.adv()
			if self.current == TT.LEFT_PARENTHESIS:
				self.adv()
				args = []
				while self.current.typ != TT.RIGHT_PARENTHESIS:
					args.append(self.parse_expression())
					if self.current.typ == TT.RIGHT_PARENTHESIS:
						break
					if self.current.typ != TT.COMMA:
						print(f"ERROR: {self.current.loc} expected ', ' or ')' ", file=stderr)
						sys.exit(37)
					self.adv()
				self.adv()
				return nodes.FunctionCall(name, args)
			return nodes.ReferTo(name)
		elif self.current == TT.KEYWORD: # constant singletons like True, False, Null
			name = self.adv()
			return nodes.Constant(name)
		elif self.current == TT.DOLLAR_SIGN:# cast
			loc = self.adv().loc
			def err() -> NoReturn:
				print(f"ERROR: {self.current.loc} expected ')' after expression in cast", file=stderr)
				sys.exit(38)
			if self.current == TT.LEFT_PARENTHESIS:#the sneaky str conversion
				self.adv()
				length = self.parse_expression()
				if self.current != TT.COMMA:
					print(f"ERROR: {self.current.loc} expected ',' in str conversion", file=stderr)
					sys.exit(39)
				self.adv()
				pointer = self.parse_expression()
				if self.current == TT.COMMA:self.adv()
				if self.current != TT.RIGHT_PARENTHESIS:err()
				self.adv()
				return nodes.StrCast(loc,length,pointer)
			typ = self.parse_type()
			if self.current.typ != TT.LEFT_PARENTHESIS:
				print(f"ERROR: {self.current.loc} expected '(' after type in cast", file=stderr)
				sys.exit(40)
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:err()
			self.adv()
			return nodes.Cast(loc,typ,expr)
		else:
			print(f"ERROR: {self.current.loc} Unexpected token while parsing term", file=stderr)
			sys.exit(41)
