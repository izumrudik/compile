import os
from typing import Callable, NoReturn, TypeVar

from .primitives import nodes, Node, TT, Token, Config, Type, types, JARARACA_PATH, BUILTIN_WORDS, ET, add_error, create_critical_error
from .utils import extract_module_from_file_name

class Parser:
	__slots__ = ('words', 'config', 'idx', 'parsed_tops', 'module_path')
	def __init__(self, words:list[Token], config:Config, module_path:str) -> None:
		self.words      :list[Token] = words
		self.config     :Config      = config
		self.idx        :int         = 0
		self.parsed_tops:list[Node]  = []
		self.module_path:str         = module_path
	def adv(self) -> Token:
		"""advance current word, and return what was current"""
		ret = self.current
		self.idx+=1
		return ret
	@property
	def current(self) -> Token:
		return self.words[self.idx]
	def parse(self) -> nodes.Module:
		#first, include std.builtin's if I am not std.builtin
		if self.module_path != 'std.builtin':
			builtins = extract_module_from_file_name(os.path.join(JARARACA_PATH,'std','builtin.ja'),self.config,'std.builtin')
			self.parsed_tops.append(nodes.FromImport('std.builtin', '<built-in>', builtins, BUILTIN_WORDS, self.current.loc))

		while self.current == TT.NEWLINE:
			self.adv() # skip newlines
		while self.current.typ != TT.EOF:
			top = self.parse_top()
			if top is not None:
				self.parsed_tops.append(top)
			while self.current == TT.NEWLINE:
				self.adv() # skip newlines
		return nodes.Module(tuple(self.parsed_tops),self.module_path)
	def parse_top(self) -> 'Node|None':
		if self.current.equals(TT.KEYWORD, 'fun'):
			return self.parse_fun()
		elif self.current.equals(TT.KEYWORD, 'use'):
			self.adv()
			if self.current.typ != TT.WORD:
				create_critical_error(ET.NO_USE_NAME, self.current.loc, "expected a name of a function to use")
			name = self.adv()
			#name(type, type) -> type
			if self.current.typ != TT.LEFT_PARENTHESIS:
				create_critical_error(ET.NO_USE_PAREN, self.current.loc, "expected '(' after 'use' keyword and a function name")
			self.adv()
			input_types:list[Type] = []
			while self.current != TT.RIGHT_PARENTHESIS:
				input_types.append(self.parse_type())
				if self.current == TT.RIGHT_PARENTHESIS:
					break
				if self.current != TT.COMMA:
					create_critical_error(ET.NO_USE_COMMA, self.current.loc, "expected ',' or ')'")
				self.adv()
			self.adv()
			output_type:Type = types.VOID
			if self.current.typ == TT.ARROW: # provided any output types
				self.adv()
				output_type = self.parse_type()
			return nodes.Use(name, tuple(input_types), output_type)
		elif self.current.equals(TT.KEYWORD, 'const'):
			self.adv()
			if self.current.typ != TT.WORD:
				create_critical_error(ET.NO_CONST_NAME, self.current.loc, "expected name of constant after keyword 'const'")
			name = self.adv()
			value = self.parse_CTE()
			return nodes.Const(name, value)
		elif self.current.equals(TT.KEYWORD, 'import'):
			self.adv()
			path,nam,module = self.parse_module_path()
			return nodes.Import(path,nam,module)
		elif self.current.equals(TT.KEYWORD, 'from'):
			loc = self.adv().loc
			path,nam,module = self.parse_module_path()
			if not self.current.equals(TT.KEYWORD, 'import'):
				create_critical_error(ET.NO_FROM_IMPORT, self.current.loc, "expected keyword 'import' after path in 'from ... import ...' top")
			self.adv()
			if self.current != TT.WORD:
				create_critical_error(ET.NO_FROM_NAME, self.current.loc, "expected word, to import after keyword 'import' in 'from ... import ...' top")
			names = [self.adv().operand]
			while self.current == TT.COMMA:
				self.adv()
				if self.current != TT.WORD:
					create_critical_error(ET.NO_FROM_2NAME, self.current.loc, "expected word, to import after comma in 'from ... import ...' top")
				names.append(self.adv().operand)
			return nodes.FromImport(path,nam,module,tuple(names),loc)

		elif self.current.equals(TT.KEYWORD, 'struct'):
			loc = self.adv().loc
			if self.current.typ != TT.WORD:
				create_critical_error(ET.NO_STRUCT_NAME, self.current.loc, "expected name of a structure after keyword 'struct'")
			name = self.adv()
			generics = self.parse_possible_generics()
			static:list[nodes.Assignment] = []
			vars:list[nodes.TypedVariable] = []
			functions:list[nodes.Fun] = []
			for var in self.block_parse_helper(self.parse_struct_statement):
				if isinstance(var,nodes.Assignment):
					static.append(var)
				elif isinstance(var,nodes.TypedVariable):
					vars.append(var)
				elif isinstance(var,nodes.Fun):
					functions.append(var)
				else:
					assert False, "unreachable"
			return nodes.Struct(loc, name, tuple(vars), tuple(static), tuple(functions), tuple(generics))
		elif self.current.equals(TT.KEYWORD, 'mix'):
			loc = self.adv().loc
			if self.current.typ != TT.WORD:
				create_critical_error(ET.NO_MIX_NAME, self.current.loc, "expected name of mix after keyword 'mix'")
			name = self.adv()
			funs = self.block_parse_helper(self.parse_mix_statement)
			return nodes.Mix(loc,name,tuple(funs))

		else:
			create_critical_error(ET.UNRECOGNIZED_TOP, self.current.loc, "unrecognized top-level entity while parsing")
	def parse_mix_statement(self) -> 'nodes.ReferTo':
		if self.current != TT.WORD:
			create_critical_error(ET.NO_MIX_MIXED_NAME, self.current.loc, "expected name of a function while parsing mix")
		return self.parse_reference()
	def parse_module_path(self) -> 'tuple[str,str,nodes.Module]':
		if self.current.typ != TT.WORD:
			create_critical_error(ET.NO_PACKET_NAME, self.current.loc, "expected name of a packet at the start of module path")
		next_level = self.adv().operand
		path:str = next_level
		link_path = os.path.join(JARARACA_PATH,'packets',next_level+'.link')
		if not os.path.exists(link_path):
			create_critical_error(ET.NO_PACKET, self.current.loc, f"packet '{path}' was not found in at '{link_path}'")
		with open(link_path,'r') as f:
			file_path = f.read()

		while self.current == TT.DOT:
			if not os.path.isdir(file_path):
				create_critical_error(ET.NO_DIR, self.current.loc, f"module '{path}' was not found in at '{file_path}'")
			self.adv()
			if self.current.typ != TT.WORD:
				create_critical_error(ET.NO_MODULE_NAME, self.current.loc, "expected name of the next module in the hierarchy after dot")
			next_level = self.adv().operand
			path += '.' + next_level
			file_path = os.path.join(file_path,next_level)
		if not os.path.isdir(file_path):
			file_path += '.ja'
		else:
			file_path = os.path.join(file_path,'__init__.ja')
		if not os.path.exists(file_path):
			create_critical_error(ET.NO_MODULE, self.current.loc, f"module '{path}' was not found at '{file_path}'")
		try:
			module = extract_module_from_file_name(file_path,self.config,path)
		except RecursionError:
			create_critical_error(ET.RECURSION, self.current.loc, f"module '{path}' was not found at '{file_path}'")
		return path,next_level,module
	def parse_possible_generics(self) -> tuple[types.Generic, ...]:
		#~generics, ...~
		generics = []
		if self.current == TT.TILDE:
			self.adv()
			while self.current != TT.TILDE:
				if self.current != TT.PERCENT:
					add_error(ET.NO_GENERIC_PERCENT, self.current.loc, "expected '%' as prefix before generic name")
				else:
					self.adv()
				if self.current != TT.WORD:
					create_critical_error(ET.NO_GENERIC_NAME, self.current.loc, "expected name of generic type after '%' in '~%name,...~'")
				generics.append(types.Generic(self.adv().operand))
				if self.current != TT.COMMA:
					break
				self.adv()
			self.adv()
		return tuple(generics)
	def parse_fun(self) -> nodes.Fun:
		self.adv()
		if self.current.typ != TT.WORD:
			create_critical_error(ET.NO_FUN_NAME, self.current.loc, "expected name of a function after keyword 'fun'")
		name = self.adv()
		
		generics = self.parse_possible_generics()
		if self.current != TT.LEFT_PARENTHESIS:
			add_error(ET.NO_FUN_PAREN, self.current.loc, "expected '(' after function name")
		else:
			self.adv()
		input_types:list[nodes.TypedVariable] = []
		while self.current != TT.RIGHT_PARENTHESIS:
			input_types.append(self.parse_typed_variable())
			if self.current == TT.RIGHT_PARENTHESIS:
				break
			if self.current != TT.COMMA:
				add_error(ET.NO_FUN_COMMA, self.current.loc, "expected ',' or ')'")
			else:
				self.adv()
		self.adv()
		output_type:Type = types.VOID
		if self.current.typ == TT.ARROW: # provided any output types
			self.adv()
			output_type = self.parse_type()
		code = self.parse_code_block()
		return nodes.Fun(name, tuple(generics), tuple(input_types), output_type, code)

	def parse_struct_statement(self) -> 'nodes.TypedVariable|nodes.Assignment|nodes.Fun':
		if self.next is not None:
			if self.next == TT.COLON:
				var = self.parse_typed_variable()
				if self.current == TT.EQUALS:
					self.adv()
					expr = self.parse_expression()
					return nodes.Assignment(var,expr)
				return var
		if self.current.equals(TT.KEYWORD, 'fun'):
			return self.parse_fun()
		create_critical_error(ET.UNRECOGNIZED_STRUCT_STATEMENT, self.current.loc, "unrecognized struct statement")
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
									return find_a_const(list(top.module.tops))
					return None
				i = find_a_const(self.parsed_tops)
				if i is not None: return i
			create_critical_error(ET.UNRECOGNIZED_CTE_TERM, self.current.loc, "unrecognized compile-time-evaluation term")
		operations = (
			TT.PLUS,
			TT.MINUS,

			TT.ASTERISK,

			TT.DOUBLE_SLASH,
			TT.PERCENT,
		)
		left:int = parse_term_int_CTE()
		while self.current.typ in operations:
			op_token = self.adv()
			right = parse_term_int_CTE()
			if   op_token == TT.PLUS        : left = left +  right
			elif op_token == TT.MINUS       : left = left -  right
			elif op_token == TT.ASTERISK    : left = left *  right
			elif op_token == TT.DOUBLE_SLASH:
				if right == 0:
					create_critical_error(ET.CTE_ZERO_DIV, self.current.loc, "division by zero")
				left = left // right
			elif op_token == TT.PERCENT:
				if right == 0:
					create_critical_error(ET.CTE_ZERO_MOD, self.current.loc, "modulo by zero")
				left = left %  right
			else:
				create_critical_error(ET.UNRECOGNIZED_CTE_OP, self.current.loc, f"unrecognized compile-time-evaluation operation '{op_token}'")
		return left
	def parse_code_block(self) -> nodes.Code:
		return nodes.Code(self.block_parse_helper(self.parse_statement))
	@property
	def next(self) -> 'Token | None':
		if len(self.words)>self.idx+1:
			return self.words[self.idx+1]
		return None
	def parse_statement(self) -> 'Node':
		if self.next is not None:#variables
			if self.next == TT.COLON:
				var = self.parse_typed_variable()
				if self.current.typ != TT.EQUALS:#var:type
					return nodes.Declaration(var)
				#var:type = value
				self.adv()
				value = self.parse_expression()
				return nodes.Assignment(var, value)
			if self.next == TT.EQUALS:
				if self.current == TT.WORD:
					variable = self.adv()
					loc = self.adv().loc# name = expression
					value = self.parse_expression()
					return nodes.VariableSave(variable,value,loc)
		if self.current == TT.LEFT_SQUARE_BRACKET:
			self.adv()
			times = self.parse_expression()
			if self.current != TT.RIGHT_SQUARE_BRACKET:
				add_error(ET.NO_DECLARATION_BRACKET, self.current.loc, "expected ']'")
			else:
				self.adv()
			var = self.parse_typed_variable()
			return nodes.Declaration(var,times)
		if self.current.equals(TT.KEYWORD, 'if'):
			return self.parse_if()
		if self.current.equals(TT.KEYWORD, 'set'):
			self.adv()
			if self.current != TT.WORD:
				create_critical_error(ET.NO_SET_NAME, self.current.loc, "expected name after keyword 'set'")
			name = self.adv()
			if self.current != TT.EQUALS:
				create_critical_error(ET.NO_SET_EQUALS, self.current.loc, "expected '=' after name and keyword 'set'")
			self.adv()
			expr = self.parse_expression()
			return nodes.Alias(name,expr)
		if self.current.equals(TT.KEYWORD, 'while'):
			return self.parse_while()
		elif self.current.equals(TT.KEYWORD, 'return'):
			loc = self.adv().loc
			return nodes.Return(loc,self.parse_expression())
		expr = self.parse_expression()
		if self.current == TT.EQUALS:
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
			create_critical_error(ET.NO_TYPED_VAR_NAME, self.current.loc, "expected variable name in typed variable")
		name = self.adv()
		if self.current.typ != TT.COLON:
			add_error(ET.NO_COLON, self.current.loc, "expected colon ':'")
		else:
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
			out:Type|None = const.get(self.current.operand) # for now that is enough

			if out is None:
				name = self.adv().operand
				#parse ~type,type,...~
				if self.current != TT.TILDE:
					return types.Struct(name,())
				self.adv()
				generics = []
				while self.current != TT.TILDE:
					generics.append(self.parse_type())
					if self.current != TT.COMMA:
						break
					self.adv()
				self.adv()
				return types.Struct(name,tuple(generics))

			self.adv()
			return out
		elif self.current == TT.LEFT_SQUARE_BRACKET:#array
			self.adv()
			if self.current == TT.RIGHT_SQUARE_BRACKET:
				size = 0
			else:
				size = self.parse_CTE()
			if self.current != TT.RIGHT_SQUARE_BRACKET:
				add_error(ET.NO_ARRAY_BRACKET, self.current.loc, "expected ']', '[' was opened and never closed")
			else:
				self.adv()
			typ = self.parse_type()
			return types.Array(typ,size)
		elif self.current.typ == TT.LEFT_PARENTHESIS:
			self.adv()
			input_types:list[Type] = []
			while self.current != TT.RIGHT_PARENTHESIS:
				input_types.append(self.parse_type())
				if self.current == TT.RIGHT_PARENTHESIS:
					break
				if self.current != TT.COMMA:
					add_error(ET.NO_FUN_TYP_COMMA, self.current.loc, "expected ',' or ')'")
				else:
					self.adv()
			self.adv()
			return_type:Type = types.VOID
			if self.current.typ == TT.ARROW: # provided any output types
				self.adv()
				return_type = self.parse_type()
			return types.Fun(tuple(input_types),return_type)
		elif self.current == TT.ASTERISK:
			self.adv()
			out = self.parse_type()
			return types.Ptr(out)
		#%T
		elif self.current == TT.PERCENT:
			self.adv()
			if self.current != TT.WORD:
				create_critical_error(ET.NO_GENERIC_TYPE_NAME, self.current.loc, "expected generic type name")
			name = self.adv().operand
			return types.Generic(name)
		else:
			create_critical_error(ET.UNRECOGNIZED_TYPE, self.current.loc, "Unrecognized type")

	def parse_expression(self) -> 'Node':
		return self.parse_exp0()
	T = TypeVar('T')
	def block_parse_helper(
		self,
		parse_statement:Callable[[], T]
			) -> tuple[T, ...]:
		if self.current.typ != TT.LEFT_CURLY_BRACKET:
			add_error(ET.NO_BLOCK_START, self.current.loc, "expected block starting with '{{'")
		else:
			self.adv()
		statements = []
		while self.current.typ in (TT.SEMICOLON,TT.NEWLINE):
			self.adv()
		while self.current != TT.RIGHT_CURLY_BRACKET:
			statement = parse_statement()
			statements.append(statement)
			if self.current == TT.RIGHT_CURLY_BRACKET:
				break
			if self.current.typ not in (TT.SEMICOLON,TT.NEWLINE):
				create_critical_error(ET.NO_NEWLINE, self.current.loc, "expected newline, ';' or '}}'")
			while self.current.typ in (TT.SEMICOLON,TT.NEWLINE):
				self.adv()
		self.adv()
		return tuple(statements)
	def bin_exp_parse_helper(
		self,
		next_exp:Callable[[], Node],
		operations:list[TT]
			) -> Node:
		left = next_exp()
		while self.current.typ in operations:
			op_token = self.adv()
			right = next_exp()
			left = nodes.BinaryExpression(left, op_token, right)
		return left

	def parse_exp0(self) -> 'Node':
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

	def parse_exp1(self) -> 'Node':
		next_exp = self.parse_exp2
		return self.bin_exp_parse_helper(next_exp, [
			TT.LESS,
			TT.GREATER,
			TT.DOUBLE_EQUALS,
			TT.NOT_EQUALS,
			TT.LESS_OR_EQUAL,
			TT.GREATER_OR_EQUAL,
		])

	def parse_exp2(self) -> 'Node':
		next_exp = self.parse_exp3
		return self.bin_exp_parse_helper(next_exp, [
			TT.PLUS,
			TT.MINUS,
		])
	def parse_exp3(self) -> 'Node':
		next_exp = self.parse_exp4
		return self.bin_exp_parse_helper(next_exp, [
			TT.DOUBLE_SLASH,
			TT.ASTERISK,
		])
	def parse_exp4(self) -> 'Node':
		next_exp = self.parse_exp5
		return self.bin_exp_parse_helper(next_exp, [
			TT.DOUBLE_GREATER,
			TT.DOUBLE_LESS,
			TT.PERCENT,
		])
	def parse_exp5(self) -> 'Node':
		self_exp = self.parse_exp5
		next_exp = self.parse_exp6
		operations = (
			TT.NOT,
			TT.AT,
		)
		if self.current.typ in operations:
			op_token = self.adv()
			right = self_exp()
			return nodes.UnaryExpression(op_token, right)
		return next_exp()

	def parse_exp6(self) -> 'Node':
		next_exp = self.parse_term
		left = next_exp()
		while self.current.typ in (TT.DOT,TT.LEFT_SQUARE_BRACKET, TT.LEFT_PARENTHESIS):
			if self.current == TT.DOT:
				loc = self.adv().loc
				if self.current != TT.WORD:
					create_critical_error(ET.NO_FIELD_NAME, self.current.loc, "expected word after '.'")
				access = self.adv()
				left = nodes.Dot(left, access,loc)
			elif self.current == TT.LEFT_SQUARE_BRACKET:
				loc = self.adv().loc
				idx = self.parse_expression()
				if self.current != TT.RIGHT_SQUARE_BRACKET:
					add_error(ET.NO_SUBSCRIPT_BRACKET, self.current.loc, "expected ']', '[' was opened and never closed")
				else:
					self.adv()
				left = nodes.Subscript(left, idx, loc)
			elif self.current == TT.LEFT_PARENTHESIS:
				loc = self.adv().loc
				args = []
				while self.current.typ != TT.RIGHT_PARENTHESIS:
					args.append(self.parse_expression())
					if self.current.typ == TT.RIGHT_PARENTHESIS:
						break
					if self.current.typ != TT.COMMA:
						add_error(ET.NO_CALL_COMMA, self.current.loc, "expected ',' or ')'")
					else:
						self.adv()
				self.adv()
				left = nodes.Call(loc,left, tuple(args))
		return left
	def parse_reference(self) -> nodes.ReferTo:
		if self.current != TT.WORD:
			create_critical_error(ET.NO_WORD_REF, self.current.loc, "expected word to refer to")
		name = self.adv()
		#parse name~type,type,...~
		generics:list[Type] = []
		if self.current == TT.TILDE:
			self.adv()
			while self.current.typ != TT.TILDE:
				generics.append(self.parse_type())
				if self.current.typ == TT.TILDE:
					break
				if self.current.typ != TT.COMMA:
					add_error(ET.NO_GENERIC_COMMA, self.current.loc, "expected ',' or '~'")
				else:
					self.adv()
			self.adv()
		return nodes.ReferTo(name, tuple(generics))
	def parse_term(self) -> 'Node':
		if self.current == TT.STRING: return nodes.Str(self.adv())
		if self.current == TT.INTEGER: return nodes.Int(self.adv())
		if self.current == TT.SHORT: return nodes.Short(self.adv())
		if self.current == TT.CHARACTER: return nodes.Char(self.adv())
		elif self.current.typ == TT.LEFT_PARENTHESIS:
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:
				add_error(ET.NO_EXPR_PAREN, self.current.loc, "expected ')'")
			else:
				self.adv()
			return expr
		elif self.current == TT.WORD: #name
			return self.parse_reference()
		elif self.current == TT.KEYWORD: # constant singletons like True, False, Null
			name = self.adv()
			return nodes.Constant(name)
		elif self.current == TT.DOLLAR:# cast
			loc = self.adv().loc
			def err() -> NoReturn:
				create_critical_error(ET.NO_CAST_RPAREN, loc, "expected ')' after expression in cast")

			if self.current == TT.LEFT_PARENTHESIS:#the sneaky str conversion
				self.adv()
				length = self.parse_expression()
				if self.current != TT.COMMA:
					add_error(ET.NO_CAST_COMMA, self.current.loc, "expected ',' in str conversion")
				else:
					self.adv()
				pointer = self.parse_expression()
				if self.current == TT.COMMA:self.adv()
				if self.current != TT.RIGHT_PARENTHESIS:err()
				self.adv()
				return nodes.StrCast(loc,length,pointer)
			typ = self.parse_type()
			if self.current.typ != TT.LEFT_PARENTHESIS:
				add_error(ET.NO_CAST_LPAREN, self.current.loc, "expected '(' after type in cast")
			else:
				self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:err()
			self.adv()
			return nodes.Cast(loc,typ,expr)
		else:
			create_critical_error(ET.NO_TERM, self.current.loc, "Unrecognized term")
