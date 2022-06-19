import os
from typing import Callable, TypeVar

from .primitives import nodes, Node, TT, Token, Config, Type, types, JARARACA_PATH, BUILTIN_WORDS, ET, Place, MAIN_MODULE_PATH
from .utils import extract_module_from_file_path
class Parser:
	__slots__ = ('tokens', 'config', 'idx', 'parsed_tops', 'module_path', 'builtin_module')
	def __init__(self, tokens:list[Token], config:Config, module_path:str|None = None) -> None:
		self.tokens     :list[Token] = tokens
		self.config     :Config      = config
		self.idx        :int         = 0
		self.parsed_tops:list[Node]  = []
		self.module_path:str         = MAIN_MODULE_PATH if module_path is None else module_path
		self.builtin_module          = extract_module_from_file_path(os.path.join(JARARACA_PATH,'std','builtin.ja'),self.config,'std.builtin', None) if self.module_path != 'std.builtin' else None
	def adv(self) -> Token:
		"""advance current word, and return what was current"""
		ret = self.current
		self.idx+=1
		return ret
	@property
	def current(self) -> Token:
		if self.idx >= len(self.tokens):
			return self.tokens[-1]
		return self.tokens[self.idx]
	def parse(self) -> nodes.Module:
		while self.current.typ != TT.EOF:
			while self.current == TT.NEWLINE:self.adv() # skip newlines
			top = self.parse_top()
			if top is None:
				continue
			if self.current != TT.NEWLINE:
				self.config.errors.add_error(ET.TOP_NEWLINE, self.current.place, f"there should be newline after every top")
			self.parsed_tops.append(top)
			while self.current == TT.NEWLINE:self.adv() # skip newlines
		return nodes.Module(tuple(self.parsed_tops),self.module_path, self.builtin_module)
	def parse_top(self) -> 'Node|None':
		if self.current.equals(TT.KEYWORD, 'fun'):
			return self.parse_fun()
		elif self.current.equals(TT.KEYWORD, 'use'):
			start_loc = self.adv().place.start
			if self.current.typ != TT.WORD:
				return self.config.errors.add_error(ET.USE_NAME, self.current.place, "expected a name of a function to use")
			name = self.adv()
			#name(type, type) -> type
			if self.current.typ != TT.LEFT_PARENTHESIS:
				self.config.errors.add_error(ET.USE_PAREN, self.current.place, "expected '(' after 'use' keyword and a function name")
			else:
				self.adv()
			input_types:list[Type] = []
			while self.current != TT.RIGHT_PARENTHESIS:
				ty = self.parse_type()
				if ty is None:
					return None
				typ, _ = ty
				input_types.append(typ)
				if self.current == TT.RIGHT_PARENTHESIS:
					break
				if self.current != TT.COMMA:
					self.config.errors.add_error(ET.USE_COMMA, self.current.place, "expected ',' or ')'")
				else:
					self.adv()
			self.adv()
			if self.current.typ != TT.ARROW: # provided any output types
				self.config.errors.add_error(ET.USE_ARROW, self.current.place, "expected '->'")
			else:
				self.adv()
			ty = self.parse_type()
			if ty is None: return ty
			output_type,place = ty
			return nodes.Use(name, tuple(input_types), output_type, Place(start_loc, place.end))
		elif self.current.equals(TT.KEYWORD, 'var'):
			start_loc = self.adv().place.start
			if self.current.typ != TT.WORD:
				return self.config.errors.add_error(ET.VAR_NAME,self.current.place, "expected name of var after keyword 'var'")
			name = self.adv()
			ty = self.parse_type()
			if ty is None: return ty
			typ,place = ty
			return nodes.Var(name, typ, Place(start_loc, place.end))
		elif self.current.equals(TT.KEYWORD, 'const'):
			start_loc = self.adv().place.start
			if self.current.typ != TT.WORD:
				return self.config.errors.add_error(ET.CONST_NAME, self.current.place, "expected name of constant after keyword 'const'")
			name = self.adv()
			cte = self.parse_CTE()
			if cte is None: return None
			value, place = cte
			return nodes.Const(name, value, Place(start_loc, place.end))
		elif self.current.equals(TT.KEYWORD, 'import'):
			start_loc = self.adv().place.start
			mp = self.parse_module_path()
			if mp is None: return None
			path,nam,module,place = mp
			return nodes.Import(path,place,nam,module, Place(start_loc, place.end))
		elif self.current.equals(TT.KEYWORD, 'from'):
			start_loc = self.adv().place.start
			mp = self.parse_module_path()
			if mp is None: return None
			path,_,module,path_place = mp
			if not self.current.equals(TT.KEYWORD, 'import'):
				self.config.errors.add_error(ET.FROM_IMPORT, self.current.place, "expected keyword 'import' after path in 'from ... import ...' top")
			else:
				self.adv()
			if self.current != TT.WORD:
				return self.config.errors.add_error(ET.FROM_NAME, self.current.place, "expected word, to import after keyword 'import' in 'from ... import ...' top")
				
			name = self.adv()
			names = [name]
			while self.current == TT.COMMA:
				self.adv()
				if self.current != TT.WORD:
					return self.config.errors.add_error(ET.FROM_2NAME, self.current.place, "expected word, to import after comma in 'from ... import ...' top")
				name = self.adv()
				names.append(name)
			return nodes.FromImport(path,path_place,module,tuple(names),Place(start_loc,name.place.end))

		elif self.current.equals(TT.KEYWORD, 'struct'):
			start_loc = self.adv().place.start
			if self.current.typ != TT.WORD:
				return self.config.errors.add_error(ET.STRUCT_NAME, self.current.place, "expected name of a structure after keyword 'struct'")
			name = self.adv()
			static:list[nodes.Assignment] = []
			vars:list[nodes.TypedVariable] = []
			functions:list[nodes.Fun] = []
			statements,place = self.block_parse_helper(self.parse_struct_statement)
			for statement in statements:
				if isinstance(statement,nodes.Assignment):
					static.append(statement)
				elif isinstance(statement,nodes.TypedVariable):
					vars.append(statement)
				elif isinstance(statement,nodes.Fun):
					functions.append(statement)
				else:
					assert False, "unreachable"
			return nodes.Struct(name, tuple(vars), tuple(static), tuple(functions), Place(start_loc, place.end))
		elif self.current.equals(TT.KEYWORD, 'mix'):
			start_loc = self.adv().place.start
			if self.current.typ != TT.WORD:
				return self.config.errors.add_error(ET.MIX_NAME, self.current.place, "expected name of mix after keyword 'mix'")
			name = self.adv()
			funs,place = self.block_parse_helper(self.parse_mix_statement)
			return nodes.Mix(name,tuple(funs), Place(start_loc, place.end))

		else:
			return self.config.errors.add_error(ET.TOP, self.adv().place, "unrecognized top-level entity while parsing")
	def parse_mix_statement(self) -> 'nodes.ReferTo|None':
		if self.current != TT.WORD:
			return self.config.errors.add_error(ET.MIX_MIXED_NAME, self.current.place, "expected name of a function while parsing mix")
		return self.parse_reference()
	def parse_module_path(self) -> 'tuple[str,str,nodes.Module,Place]|None':
		if self.current.typ != TT.WORD:
			return self.config.errors.add_error(ET.PACKET_NAME, self.current.place, "expected name of a packet at the start of module path")
		next_token = self.adv()
		path_start = next_token.place.start
		path:str = next_token.operand
		link_path = os.path.join(JARARACA_PATH,'packets',path+'.link')
		if not os.path.exists(link_path):
			return self.config.errors.add_error(ET.PACKET, next_token.place, f"packet '{path}' was not found at '{link_path}'")
		with open(link_path,'r') as f:
			file_path = f.read()

		while self.current == TT.DOT:
			if not os.path.isdir(file_path):
				return self.config.errors.add_error(ET.DIR, next_token.place, f"module '{path}' was not found at '{file_path}'")
			self.adv()
			if self.current.typ != TT.WORD:
				return self.config.errors.add_error(ET.MODULE_NAME, self.current.place, "expected name of the next module in the hierarchy after dot")
			next_token = self.adv()
			next_level = next_token.operand
			path += '.' + next_level
			file_path = os.path.join(file_path,next_level)
		if not os.path.isdir(file_path):
			file_path += '.ja'
		else:
			file_path = os.path.join(file_path,'__init__.ja')
		place = Place(path_start, next_token.place.end)
		module = extract_module_from_file_path(file_path,self.config,path, place)
		return path,next_level,module,place
	def parse_fun(self) -> nodes.Fun|None:
		start_loc = self.adv().place.start
		if self.current.typ != TT.WORD:
			return self.config.errors.add_error(ET.FUN_NAME, self.current.place, "expected name of a function after keyword 'fun'")
		name = self.adv()
		args_place_start = self.current.place.start
		if self.current != TT.LEFT_PARENTHESIS:
			self.config.errors.add_error(ET.FUN_PAREN, self.current.place, "expected '(' after function name")
		else:
			self.adv()
		input_types:list[nodes.TypedVariable] = []
		while self.current != TT.RIGHT_PARENTHESIS:
			tv = self.parse_typed_variable()
			if tv is not None:
				input_types.append(tv)
			if self.current == TT.RIGHT_PARENTHESIS:
				break
			if self.current != TT.COMMA:
				self.config.errors.add_error(ET.FUN_COMMA, self.current.place, "expected ',' or ')'")
			else:
				self.adv()
		args_place_end = self.adv().place.end
		output_type:Type = types.VOID
		return_type_place = None
		if self.current.typ == TT.ARROW: # provided any output types
			self.adv()
			ty = self.parse_type()
			if ty is None: return None
			output_type,return_type_place = ty
		code = self.parse_code_block()
		return nodes.Fun(name, tuple(input_types), output_type, code, Place(args_place_start, args_place_end), return_type_place, Place(start_loc, code.place.end))

	def parse_struct_statement(self) -> 'nodes.TypedVariable|nodes.Assignment|nodes.Fun|None':
		if self.next is not None:
			if self.next == TT.COLON:
				var = self.parse_typed_variable()
				if var is None: return None
				if self.current == TT.EQUALS:
					self.adv()
					expr = self.parse_expression()
					if expr is None: return None
					return nodes.Assignment(var,expr, Place(var.place.start, expr.place.end))
				return var
		if self.current.equals(TT.KEYWORD, 'fun'):
			return self.parse_fun()
		return self.config.errors.add_error(ET.STRUCT_STATEMENT, self.adv().place, "unrecognized struct statement")
	def parse_CTE(self) -> tuple[int,Place]|None:
		def parse_term_int_CTE() -> tuple[int,Place]|None:
			if self.current == TT.INT:
				c = self.adv()
				return int(c.operand), c.place
			if self.current == TT.WORD:
				def find_a_const(tops:list[Node]) -> int|None:
					if self.current.operand in BUILTIN_WORDS and self.builtin_module is not None:
						return find_a_const(list(self.builtin_module.tops))
					for top in tops:#FIXME
						if isinstance(top, nodes.Const):
							if top.name == self.current:
								return top.value
						if isinstance(top, nodes.FromImport):
							for name in top.imported_names:
								if name == self.current:
									return find_a_const(list(top.module.tops))
					return None
				i = find_a_const(self.parsed_tops)
				if i is not None:
					return i, self.adv().place
			return self.config.errors.add_error(ET.CTE_TERM, self.adv().place, "unrecognized compile-time-evaluation term")
		operations = (
			TT.PLUS,
			TT.MINUS,

			TT.ASTERISK,

			TT.DOUBLE_SLASH,
			TT.PERCENT,
		)
		cte = parse_term_int_CTE()
		if cte is None: return None
		left,place = cte
		start_loc = place.start
		end_loc = place.end
		while self.current.typ in operations:
			op_token = self.current.typ
			self.adv()
			cte = parse_term_int_CTE()
			if cte is None: return None
			right,place = cte
			end_loc = place.end
			if   op_token == TT.PLUS        : left = left +  right
			elif op_token == TT.MINUS       : left = left -  right
			elif op_token == TT.ASTERISK    : left = left *  right
			elif op_token == TT.DOUBLE_SLASH:
				if right == 0:
					self.config.errors.add_error(ET.CTE_ZERO_DIV, self.current.place, "division by zero in cte")
				else:
					left = left // right
			elif op_token == TT.PERCENT:
				if right == 0:
					self.config.errors.add_error(ET.CTE_ZERO_MOD, self.current.place, "modulo by zero in cte")
				else:
					left = left %  right
			else:
				assert False, "Unreachable"
		return left, Place(start_loc, end_loc)
	def parse_code_block(self) -> nodes.Code:
		block,place = self.block_parse_helper(self.parse_statement)
		return nodes.Code(block,place)
	@property
	def next(self) -> 'Token | None':
		if len(self.tokens)>self.idx+1:
			return self.tokens[self.idx+1]
		return None
	def parse_statement(self) -> 'Node|None':
		if self.next is not None:#variables
			if self.next == TT.COLON:
				var = self.parse_typed_variable()
				if var is None: return None
				if self.current.typ != TT.EQUALS:#var:type
					return nodes.Declaration(var,None,var.place)
				#var:type = value
				self.adv()
				value = self.parse_expression()
				if value is None: return None
				return nodes.Assignment(var, value, Place(var.place.start, value.place.end))
			if self.next == TT.EQUALS:
				if self.current == TT.WORD:
					variable = self.adv()
					self.adv()# name = expression
					value = self.parse_expression()
					if value is None: return None
					return nodes.VariableSave(variable,value, Place(variable.place.start, value.place.end))
		if self.current == TT.LEFT_SQUARE_BRACKET:
			start_loc = self.adv().place.start
			times = self.parse_expression()
			if self.current != TT.RIGHT_SQUARE_BRACKET:
				self.config.errors.add_error(ET.DECLARATION_BRACKET, self.current.place, "expected ']'")
			else:
				self.adv()
			var = self.parse_typed_variable()
			if var is None: return None
			return nodes.Declaration(var,times, Place(start_loc, var.place.end))
		if self.current.equals(TT.KEYWORD, 'if'):
			return self.parse_if()
		if self.current.equals(TT.KEYWORD, 'set'):
			start_loc = self.adv().place.start
			if self.current != TT.WORD:
				return self.config.errors.add_error(ET.SET_NAME, self.current.place, "expected name after keyword 'set'")
			name = self.adv()
			if self.current != TT.EQUALS:
				self.config.errors.add_error(ET.SET_EQUALS, self.current.place, "expected '=' after name and keyword 'set'")
			else:
				self.adv()
			expr = self.parse_expression()
			if expr is None: return None
			return nodes.Set(name,expr, Place(start_loc, expr.place.end))
		if self.current.equals(TT.KEYWORD, 'while'):
			return self.parse_while()
		elif self.current.equals(TT.KEYWORD, 'return'):
			start_loc = self.adv().place.start
			expr = self.parse_expression()
			if expr is None: return None
			return nodes.Return(expr, Place(start_loc, expr.place.end))
		expr = self.parse_expression()
		if expr is None: return None
		if self.current == TT.EQUALS:
			self.adv()
			value = self.parse_expression()
			if value is None: return None
			return nodes.Save(expr, value, Place(expr.place.start, value.place.end))
		return nodes.ExprStatement(expr, expr.place)
	def parse_if(self) -> nodes.If|None:
		start_loc = self.adv().place.start
		condition = self.parse_expression()
		if condition is None: return None
		if_code = self.parse_code_block()
		if self.current.equals(TT.KEYWORD, 'elif'):
			else_block = self.parse_if()
			if else_block is None: return None
			return nodes.If(condition, if_code, else_block, Place(start_loc, else_block.place.end))
		if self.current.equals(TT.KEYWORD, 'else'):
			self.adv()
			else_code = self.parse_code_block()
			return nodes.If(condition, if_code, else_code, Place(start_loc, else_code.place.end))
		return nodes.If(condition, if_code, None, Place(start_loc, if_code.place.end))
	def parse_while(self) -> nodes.While|None:
		start_loc = self.adv().place.start
		condition = self.parse_expression()
		if condition is None: return None			
		code = self.parse_code_block()
		return nodes.While(condition, code, Place(start_loc, code.place.end))
	def parse_typed_variable(self) -> nodes.TypedVariable|None:
		if self.current != TT.WORD:
			return self.config.errors.add_error(ET.TYPED_VAR_NAME, self.current.place, "expected variable name in typed variable")
		name = self.adv()
		if self.current.typ != TT.COLON:
			self.config.errors.add_error(ET.COLON, self.current.place, "expected colon ':'")
		else:
			self.adv()#type
		ty = self.parse_type()
		if ty is None: return None
		typ,place = ty

		return nodes.TypedVariable(name, typ, Place(name.place.start, place.end))
	def parse_type(self) -> tuple[Type,Place]|None:
		if self.current == TT.WORD:
			const = {
				'void' : types.VOID,
				'bool' : types.BOOL,
				'char' : types.CHAR,
				'short': types.SHORT,
				'str'  : types.STR,
				'int'  : types.INT,
			}
			out:Type|None = const.get(self.current.operand)

			name = self.adv()
			if out is None:
				return types.Struct(name.operand), name.place

			return out, name.place
		elif self.current == TT.LEFT_SQUARE_BRACKET:#array
			start_loc = self.adv().place.start
			if self.current == TT.RIGHT_SQUARE_BRACKET:
				size = 0
			else:
				cte = self.parse_CTE()
				if cte is None: return None
				size,_ = cte
			if self.current != TT.RIGHT_SQUARE_BRACKET:
				self.config.errors.add_error(ET.ARRAY_BRACKET, self.current.place, "expected ']', '[' was opened and never closed")
			else:
				self.adv()
			ty = self.parse_type()
			if ty is None: return None
			typ,place = ty
			return types.Array(typ,size),Place(start_loc,place.end)
		elif self.current.typ == TT.LEFT_PARENTHESIS:
			start_loc = self.adv().place.start
			input_types:list[Type] = []
			while self.current != TT.RIGHT_PARENTHESIS:
				ty = self.parse_type()
				if ty is None:return None
				typ, _ = ty
				input_types.append(typ)
				if self.current == TT.RIGHT_PARENTHESIS:
					break
				if self.current != TT.COMMA:
					self.config.errors.add_error(ET.FUN_TYP_COMMA, self.current.place, "expected ',' or ')'")
				else:
					self.adv()
			self.adv()
			if self.current.typ != TT.ARROW: # provided any output types
				self.config.errors.add_error(ET.FUNCTION_TYPE_ARROW, self.current.place, "expected '->'")
			else:
				self.adv()
			ty = self.parse_type()
			if ty is None:return None
			return_type,place = ty
			return types.Fun(tuple(input_types),return_type),Place(start_loc,place.end)
		elif self.current == TT.ASTERISK:
			start_loc = self.adv().place.start
			ty = self.parse_type()
			if ty is None:return None
			out,place = ty
			return types.Ptr(out),Place(start_loc,place.end)
		else:
			return self.config.errors.add_error(ET.TYPE, self.adv().place, "Unrecognized type")

	def parse_expression(self) -> 'Node|None':
		return self.parse_exp0()
	T = TypeVar('T')
	def block_parse_helper(
		self,
		parse_statement:Callable[[], T|None]
			) -> tuple[tuple[T, ...],Place]:
		start_loc = self.current.place.start
		if self.current.typ != TT.LEFT_CURLY_BRACKET:
			self.config.errors.add_error(ET.BLOCK_START, self.current.place, f"expected block starting with '{{'")
		else:
			self.adv()
		statements = []
		while self.current.typ == TT.NEWLINE:
			self.adv()
		while self.current != TT.RIGHT_CURLY_BRACKET:
			statement = parse_statement()
			if statement is not None:
				statements.append(statement)
			if self.current == TT.RIGHT_CURLY_BRACKET:
				break
			if self.current.typ != TT.NEWLINE:
				self.config.errors.add_error(ET.NEWLINE, self.current.place, f"expected newline or '}}'")
			while self.current.typ == TT.NEWLINE:
				self.adv()
		end_loc = self.adv().place.end
		return tuple(statements), Place(start_loc, end_loc)
	def bin_exp_parse_helper(
		self,
		next_exp:Callable[[], Node|None],
		operations:list[TT]
			) -> Node|None:
		left = next_exp()
		if left is None:return None
		while self.current.typ in operations:
			op_token = self.adv()
			right = next_exp()
			if right is None:return None
			left = nodes.BinaryExpression(left, op_token, right, Place(left.place.start, right.place.end))
		return left

	def parse_exp0(self) -> 'Node|None':
		next_exp = self.parse_exp1
		operations = [
			'or',
			'xor',
			'and',
		]
		left = next_exp()
		if left is None:return None
		while self.current == TT.KEYWORD and self.current.operand in operations:
			op_token = self.adv()
			right = next_exp()
			if right is None:return None
			left = nodes.BinaryExpression(left, op_token, right, Place(left.place.start, right.place.end))
		return left

	def parse_exp1(self) -> 'Node|None':
		next_exp = self.parse_exp2
		return self.bin_exp_parse_helper(next_exp, [
			TT.LESS,
			TT.GREATER,
			TT.DOUBLE_EQUALS,
			TT.NOT_EQUALS,
			TT.LESS_OR_EQUAL,
			TT.GREATER_OR_EQUAL,
		])

	def parse_exp2(self) -> 'Node|None':
		next_exp = self.parse_exp3
		return self.bin_exp_parse_helper(next_exp, [
			TT.PLUS,
			TT.MINUS,
		])
	def parse_exp3(self) -> 'Node|None':
		next_exp = self.parse_exp4
		return self.bin_exp_parse_helper(next_exp, [
			TT.DOUBLE_SLASH,
			TT.ASTERISK,
		])
	def parse_exp4(self) -> 'Node|None':
		next_exp = self.parse_exp5
		return self.bin_exp_parse_helper(next_exp, [
			TT.DOUBLE_GREATER,
			TT.DOUBLE_LESS,
			TT.PERCENT,
		])
	def parse_exp5(self) -> 'Node|None':
		self_exp = self.parse_exp5
		next_exp = self.parse_exp6
		operations = (
			TT.NOT,
			TT.AT,
		)
		if self.current.typ in operations:
			op_token = self.adv()
			right = self_exp()
			if right is None: return None
			return nodes.UnaryExpression(op_token, right, Place(op_token.place.start, right.place.end))
		return next_exp()

	def parse_exp6(self) -> 'Node|None':
		next_exp = self.parse_term
		left = next_exp()
		if left is None: return None
		while self.current.typ in (TT.DOT,TT.LEFT_SQUARE_BRACKET, TT.LEFT_PARENTHESIS, TT.NO_MIDDLE_TEMPLATE, TT.TEMPLATE_HEAD):
			if self.current == TT.DOT:
				self.adv()
				if self.current != TT.WORD:
					self.config.errors.add_error(ET.FIELD_NAME, self.current.place, "expected word after '.'")
				else:
					access = self.adv()
					left = nodes.Dot(left, access, Place(left.place.start, access.place.end))
			elif self.current == TT.LEFT_SQUARE_BRACKET:
				start_loc = self.adv().place.start
				subscripts:list[Node] = []
				while self.current.typ != TT.RIGHT_SQUARE_BRACKET:
					r = self.parse_expression()
					if r is not None:
						subscripts.append(r)
					if self.current.typ == TT.RIGHT_SQUARE_BRACKET:
						break
					if self.current.typ != TT.COMMA:
						self.config.errors.add_error(ET.SUBSCRIPT_COMMA, self.current.place, "expected ',' or ']'")
					else:
						self.adv()
				end_loc = self.adv().place.end
				left = nodes.Subscript(left, tuple(subscripts), Place(start_loc, end_loc), Place(left.place.start, end_loc))
			elif self.current == TT.LEFT_PARENTHESIS:
				start_loc = self.adv().place.start
				args:list[Node] = []
				while self.current.typ != TT.RIGHT_PARENTHESIS:
					r = self.parse_expression()
					if r is not None:
						args.append(r)
					if self.current.typ == TT.RIGHT_PARENTHESIS:
						break
					if self.current.typ != TT.COMMA:
						self.config.errors.add_error(ET.CALL_COMMA, self.current.place, "expected ',' or ')'")
					else:
						self.adv()
				end_loc = self.adv().place.end
				left = nodes.Call(left, tuple(args), Place(start_loc, end_loc), Place(left.place.start, end_loc))
			elif self.current.typ in (TT.NO_MIDDLE_TEMPLATE, TT.TEMPLATE_HEAD):
				left = self.parse_template_string_helper(left)
				if left is None: return None
		return left
	def parse_reference(self) -> nodes.ReferTo|None:
		if self.current != TT.WORD:
			return self.config.errors.add_error(ET.WORD_REF, self.current.place, "expected a word to refer to")
		name = self.adv()
		return nodes.ReferTo(name, name.place)
	def parse_term(self) -> 'Node|None':
		if self.current == TT.STR:     return nodes.Str     (self.current, self.adv().place)
		if self.current == TT.INT:     return nodes.Int     (self.current, self.adv().place)
		if self.current == TT.SHORT:   return nodes.Short   (self.current, self.adv().place)
		if self.current == TT.CHAR_STR:return nodes.CharStr (self.current, self.adv().place)
		if self.current == TT.CHAR_NUM:return nodes.CharNum (self.current, self.adv().place)
		if self.current == TT.KEYWORD and self.current.operand in ('False','True','Null','Argv','Argc','Void'):
			return nodes.Constant(self.current, self.adv().place)
		elif self.current.typ == TT.LEFT_PARENTHESIS:
			self.adv()
			expr = self.parse_expression()
			if self.current.typ != TT.RIGHT_PARENTHESIS:
				self.config.errors.add_error(ET.EXPR_PAREN, self.current.place, "expected ')'")
			else:
				self.adv()
			return expr
		elif self.current == TT.WORD: #name
			return self.parse_reference()
		elif self.current == TT.DOLLAR:# cast
			start_loc = self.adv().place.start
			def err() -> None:
				self.config.errors.add_error(ET.CAST_RPAREN, self.current.place, "expected ')' after expression in cast")

			if self.current == TT.LEFT_PARENTHESIS:#the sneaky str conversion
				self.adv()
				length = self.parse_expression()
				if length is None: return None
				if self.current != TT.COMMA:
					self.config.errors.add_error(ET.CAST_COMMA, self.current.place, "expected ',' in str conversion")
				else:
					self.adv()
				pointer = self.parse_expression()
				if pointer is None: return None
				if self.current == TT.COMMA:self.adv()
				end_loc = self.current.place.end
				if self.current != TT.RIGHT_PARENTHESIS:
					err()
				else:
					end_loc = self.adv().place.end
				return nodes.StrCast(length,pointer, Place(start_loc, end_loc))
			ty = self.parse_type()
			if ty is None:return None
			typ,_ = ty
			
			if self.current.typ != TT.LEFT_PARENTHESIS:
				self.config.errors.add_error(ET.CAST_LPAREN, self.current.place, "expected '(' after type in cast")
			else:
				self.adv()
			expr = self.parse_expression()
			if expr is None: return None
			end_loc = self.current.place.end
			if self.current.typ != TT.RIGHT_PARENTHESIS:
				err()
			else:
				end_loc = self.adv().place.end
			return nodes.Cast(typ,expr, Place(start_loc, end_loc))
		elif self.current.typ in (TT.NO_MIDDLE_TEMPLATE, TT.TEMPLATE_HEAD):
			return self.parse_template_string_helper(None)
		else:
			return self.config.errors.add_error(ET.TERM, self.adv().place, "Unrecognized term")
	def parse_template_string_helper(self, formatter:None|Node) -> nodes.Template|None:
		if self.current == TT.TEMPLATE_HEAD:
			strings = [self.adv()]
			r = self.parse_expression()
			if r is None: return None
			values = [r]
			while self.current.typ != TT.TEMPLATE_TAIL:
				if self.current.typ != TT.TEMPLATE_MIDDLE:
					self.config.errors.add_error(ET.TEMPLATE_R_CURLY, self.current.place, "expected '}'")
				else:
					strings.append(self.adv())
				r = self.parse_expression()
				if r is None: return None
				values.append(r)
			strings.append(self.adv())
			return nodes.Template(formatter, tuple(strings), tuple(values), Place(strings[0].place.start, strings[-1].place.end))
		elif self.current == TT.NO_MIDDLE_TEMPLATE:
			return nodes.Template(formatter, (self.current,), (), self.adv().place)
		else:
			assert False, "function above did not check for existing of template"
