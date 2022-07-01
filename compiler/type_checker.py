from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from .primitives import nodes, Node, ET, Config, Type, types, NotSaveableException, DEFAULT_TEMPLATE_STRING_FORMATTER, BUILTIN_WORDS, Place
__all__ = (
	'SemanticTokenType',
	'SemanticTokenModifier',
	'SemanticToken',
	'TypeChecker',
)
class SemanticTokenType(Enum):
	MODULE           = auto()
	STRUCT           = auto()
	ARGUMENT         = auto()
	VARIABLE         = auto()
	PROPERTY         = auto()
	FUNCTION         = auto()
	BOUND_FUNCTION   = auto()
	MIX              = auto()
	STRING           = auto()
	INTEGER          = auto()
	CHARACTER_STRING = auto()
	CHARACTER_NUMBER = auto()
	SHORT            = auto()
	OPERATOR         = auto()
	def __str__(self) -> str:
		return self.name.lower().replace('_', ' ')
class SemanticTokenModifier(Enum):
	DECLARATION  = auto()
	DEFINITION   = auto()
	STATIC       = auto()
	def __str__(self) -> str:
		return self.name.lower()
@dataclass(frozen=True, slots=True)
class SemanticToken:
	place:Place
	typ:SemanticTokenType
	modifiers:tuple[SemanticTokenModifier,...] = ()
class TypeChecker:
	__slots__ = ('config', 'module', 'modules', 'names', 'type_names', 'expected_return_type', 'semantic', 'semantic_tokens')
	def __init__(self, module:nodes.Module, config:Config, semantic:bool = False) -> None:
		self.module = module
		self.config = config
		self.names:dict[str, Type] = {}#regular definitions like `var x int`
		self.type_names:dict[str, Type] = {}#type definitions like `struct X {}`
		self.modules:dict[int, TypeChecker] = {}
		self.expected_return_type:Type = types.VOID
		self.semantic:bool = semantic
		if self.semantic:
			self.semantic_tokens:set[SemanticToken] = set()
	def go_check(self) -> None:
		if self.module.builtin_module is not None:
			tc = TypeChecker(self.module.builtin_module, self.config)
			tc.go_check()
			self.modules[self.module.builtin_module.uid] = tc
			for name in BUILTIN_WORDS:
				type_definition = tc.type_names.get(name)
				definition = tc.names.get(name)
				assert type_definition is not None or None is not definition, f"Unreachable, std.builtin does not have word '{name}' defined, but it must"
				if definition is not None:
					self.names[name] = definition
				if type_definition is not None:
					self.type_names[name] = type_definition
		for top in self.module.tops:
			if isinstance(top,nodes.Import):
				self.names[top.name] = types.Module(top.module)
				tc = TypeChecker(top.module, self.config)
				self.modules[top.module.uid] = tc
				tc.go_check()
			elif isinstance(top,nodes.FromImport):
				tc = TypeChecker(top.module, self.config)
				tc.go_check()
				self.modules[top.module.uid] = tc
				for nam in top.imported_names:
					name = nam.operand
					type_definition = tc.type_names.get(name)
					definition = tc.names.get(name)
					if type_definition is definition is None:
						self.config.errors.add_error(ET.IMPORT_NAME, top.place, f"name '{name}' is not defined in module '{top.module.path}'")
					if self.semantic:
						self.semantic_reference_helper_from_typ(definition, nam.place, (SemanticTokenModifier.DECLARATION,))
					if definition is not None:
						self.names[name] = definition
					if type_definition is not None:
						self.type_names[name] = type_definition
			elif isinstance(top,nodes.Var):
				self.names[top.name.operand] = types.Ptr(self.check(top.typ))
			elif isinstance(top,nodes.Const):
				self.names[top.name.operand] = types.INT
			elif isinstance(top, nodes.Mix):
				self.names[top.name.operand] = types.Mix(tuple(self.check(fun_ref) for fun_ref in top.funs),top.name.operand)
			elif isinstance(top,nodes.Use):
				self.names[top.as_name.operand] = types.Fun(tuple(self.check(arg) for arg in top.arg_types),self.check(top.return_type))
			elif isinstance(top,nodes.Fun):
				self.names[top.name.operand] = top.typ(self.check)
				if top.name.operand == 'main':
					if top.return_type is not None:
						if self.check(top.return_type) != types.VOID:
							self.config.errors.add_error(ET.MAIN_RETURN, top.return_type_place, f"entry point (function 'main') has to return {types.VOID}, found '{top.return_type}'")
					if len(top.arg_types) != 0:
						self.config.errors.add_error(ET.MAIN_ARGS, top.args_place, f"entry point (function 'main') has to take no arguments, found '({', '.join(map(str,top.arg_types))})'")
			elif isinstance(top,nodes.Struct):
				self.type_names[top.name.operand] = types.Struct(top)
				self.names[top.name.operand] = types.StructKind(top)

		for top in self.module.tops:
			self.check(top)
	def check_import(self, node:nodes.Import) -> Type:
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.path_place, SemanticTokenType.MODULE, (SemanticTokenModifier.DECLARATION,)))
		return types.VOID
	def check_from_import(self, node:nodes.FromImport) -> Type:
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.path_place, SemanticTokenType.MODULE, (SemanticTokenModifier.DECLARATION,)))
		return types.VOID
	def check_fun(self, node:nodes.Fun, semantic_type:SemanticTokenType = SemanticTokenType.FUNCTION) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,semantic_type,(SemanticTokenModifier.DEFINITION,)))
			for arg in node.arg_types:
				self.semantic_tokens.add(SemanticToken(arg.name.place,SemanticTokenType.ARGUMENT,(SemanticTokenModifier.DECLARATION,)))
		vars_before = self.names.copy()
		self.names.update({arg.name.operand:self.check(arg.typ) for arg in node.arg_types})
		self.expected_return_type = self.check(node.return_type) if node.return_type is not None else types.VOID
		actual_ret_typ = self.check(node.code)
		specified_ret_typ = self.check(node.return_type) if node.return_type is not None else types.VOID
		if specified_ret_typ != actual_ret_typ:
			self.config.errors.add_error(ET.FUN_RETURN, node.return_type_place, f"specified return type '{specified_ret_typ}' does not match actual return type '{actual_ret_typ}'")
		self.names = vars_before
		self.expected_return_type = types.VOID
		return types.VOID
	def check_code(self, node:nodes.Code) -> Type:
		vars_before = self.names.copy()
		ret = None
		for statement in node.statements:
			if isinstance(statement,nodes.Return):
				if ret is None:
					ret = self.check(statement)
					continue
			self.check(statement)
		self.names = vars_before #this is scoping
		if ret is None:
			return types.VOID
		return self.expected_return_type
	def check_call(self, node:nodes.Call) -> Type:
		return self.call_helper(self.check(node.func), [self.check(arg) for arg in node.args], node.place)
	def call_helper(self, function:Type, args:list[Type], place:Place) -> Type:
		def get_fun_out_of_called(called:Type) -> types.Fun:
			if isinstance(called, types.Fun):
				return called
			if isinstance(called, types.BoundFun):
				return called.apparent_typ
			if isinstance(called, types.StructKind):
				magic = called.struct.get_magic('init')
				if magic is None:
					self.config.errors.critical_error(ET.INIT_MAGIC, place, f"structure '{called}' has no '__init__' magic defined")
				return types.Fun(
					tuple(self.check(arg.typ) for arg in magic.arg_types[1:]),
					types.Ptr(types.Struct(called.struct))
				)
			if isinstance(called, types.Mix):
				for ref in called.funs:
					fun = get_fun_out_of_called(ref)
					if len(args) != len(fun.arg_types):
						continue#continue searching
					for actual_arg,arg in zip(args,fun.arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun#found fun
					continue
				self.config.errors.critical_error(ET.CALL_MIX, place, f"did not find function to match '{tuple(args)!s}' contract in mix '{called}'")
			self.config.errors.critical_error(ET.CALLABLE, place, f"'{called}' object is not callable")
		fun = get_fun_out_of_called(function)
		if len(fun.arg_types) != len(args):
			self.config.errors.critical_error(ET.CALL_ARGS, place, f"function '{fun}' accepts {len(fun.arg_types)} arguments, provided {len(args)} arguments")
		for idx, typ in enumerate(args):
			needed = fun.arg_types[idx]
			if typ != needed:
				self.config.errors.add_error(ET.CALL_ARG, place, f"function '{fun}' argument {idx} takes '{needed}', got '{typ}'")
		return fun.return_type
	def check_bin_exp(self, node:nodes.BinaryExpression) -> Type:
		left = self.check(node.left)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.operation.place,SemanticTokenType.OPERATOR))
		right = self.check(node.right)
		return node.typ(left,right, self.config)
	def check_expr_state(self, node:nodes.ExprStatement) -> Type:
		self.check(node.value)
		return types.VOID
	def check_str(self, node:nodes.Str) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.STRING))
		return types.STR
	def check_int(self, node:nodes.Int) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.INTEGER))
		return types.INT
	def check_short(self, node:nodes.Short) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.SHORT))
		return types.SHORT
	def check_char_str(self, node:nodes.CharStr) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.CHARACTER_STRING))
		return types.CHAR
	def check_char_num(self, node:nodes.CharNum) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.CHARACTER_NUMBER))
		return types.CHAR		
	def check_assignment(self, node:nodes.Assignment) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.var.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,)))
		actual_type = self.check(node.value)
		if self.check(node.var.typ) != actual_type:
			self.config.errors.add_error(ET.ASSIGNMENT, node.place, f"specified type '{node.var.typ}' does not match actual type '{actual_type}' in assignment")
		self.names[node.var.name.operand] = types.Ptr(self.check(node.var.typ))
		return types.VOID
	def semantic_reference_helper_from_typ(self, typ:Type|None, place:Place, modifiers:tuple[SemanticTokenModifier, ...] = ()) -> None:
		if self.semantic:
			if   isinstance(typ, types.Struct)    :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.STRUCT,         modifiers))
			elif isinstance(typ, types.StructKind):self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.STRUCT,         modifiers))
			elif isinstance(typ, types.Fun)       :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.FUNCTION,       modifiers))
			elif isinstance(typ, types.BoundFun)  :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.BOUND_FUNCTION, modifiers))
			elif isinstance(typ, types.Mix)       :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.MIX,            modifiers))
			elif isinstance(typ, types.Module)    :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.MODULE,         modifiers))
			else                                  :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.VARIABLE,       modifiers))
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.names.get(node.name.operand)
		if self.semantic:
			self.semantic_reference_helper_from_typ(typ, node.name.place)
		if typ is None:
			self.config.errors.critical_error(ET.REFER, node.place, f"did not find name '{node.name}'")
		return typ
	def check_declaration(self, node:nodes.Declaration) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.var.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DECLARATION,)))
		if node.times is None:
			self.names[node.var.name.operand] = types.Ptr(self.check(node.var.typ))
			return types.VOID
		times = self.check(node.times)
		if times != types.INT:
			self.config.errors.add_error(ET.DECLARATION_TIMES, node.place, f"number of elements to allocate should be an '{types.INT}', got '{times}'")
		self.names[node.var.name.operand] = types.Ptr(types.Array(self.check(node.var.typ)))
		return types.VOID
	def check_save(self, node:nodes.Save) -> Type:
		space = self.check(node.space)
		value = self.check(node.value)
		if not isinstance(space, types.Ptr):
			self.config.errors.critical_error(ET.SAVE_PTR, node.place, f"expected pointer to save into, got '{space}'")
		if space.pointed != value:
			self.config.errors.add_error(ET.SAVE, node.place, f"space type '{space}' does not match value's type '{value}'")
		return types.VOID
	def check_variable_save(self, node:nodes.VariableSave) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.space.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,)))
		space = self.names.get(node.space.operand)
		value = self.check(node.value)
		if space is None:#auto
			try:value.llvm
			except NotSaveableException:
				self.config.errors.add_error(ET.UNSAVEABLE_VSAVE, node.place, f"type '{value}' is not saveable")
			space = types.Ptr(value)
			self.names[node.space.operand] = space
		if not isinstance(space, types.Ptr):
			self.config.errors.critical_error(ET.VSAVE_PTR, node.place, f"expected pointer to save into, got '{space}'")
		if space.pointed != value:
			self.config.errors.add_error(ET.VSAVE, node.place, f"space type '{space}' does not match value's type '{value}'")
		return types.VOID
	def check_if(self, node:nodes.If) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			self.config.errors.add_error(ET.IF, node.condition.place, f"if statement expected '{types.BOOL}' type, got '{actual}'")
		if node.else_code is None:
			return self.check(node.code)
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code)
		if actual_if != actual_else:
			self.config.errors.critical_error(ET.IF_BRANCH, node.place, f"if branches are inconsistent: one branch returns while other does not (refactor without 'else')")
		return actual_if
	def check_while(self, node:nodes.While) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			self.config.errors.add_error(ET.WHILE, node.place, f"while statement expected '{types.BOOL}' type, got '{actual}'")
		return self.check(node.code)
	def check_set(self, node:nodes.Set) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,)))
		value = self.check(node.value)
		self.names[node.name.operand] = value
		return types.VOID
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.operation.place,SemanticTokenType.OPERATOR))
		return node.typ(self.check(node.left), self.config)
	def check_constant(self, node:nodes.Constant) -> Type:
		return node.typ
	def check_var(self, node:nodes.Var) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DECLARATION,)))
		return types.VOID
	def check_const(self, node:nodes.Const) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,)))
		return types.VOID
	def check_struct(self, node:nodes.Struct) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.STRUCT, (SemanticTokenModifier.DEFINITION,)))
			for var in node.variables:
				self.semantic_tokens.add(SemanticToken(var.name.place,SemanticTokenType.PROPERTY, (SemanticTokenModifier.DEFINITION,)))
		for fun in node.funs:
			self_should_be = types.Ptr(types.Struct(node))
			if len(fun.arg_types)==0:
				self.config.errors.critical_error(ET.STRUCT_FUN_ARGS, fun.args_place, f"bound function's argument 0 should be '{self_should_be}' (self), found 0 arguments")
			elif self.check(fun.arg_types[0].typ) != self_should_be:
				self.config.errors.add_error(ET.STRUCT_FUN_ARG, fun.arg_types[0].place, f"bound function's argument 0 should be '{self_should_be}' (self) got '{fun.arg_types[0].typ}'")
			rt = self.check(fun.return_type) if fun.return_type is not None else types.VOID
			if fun.name == '__str__':
				if len(fun.arg_types) != 1:
					self.config.errors.critical_error(ET.STR_MAGIC, fun.args_place, f"magic function '__str__' should have 1 argument, not {len(fun.arg_types)}")
				if rt != types.STR:
					self.config.errors.critical_error(ET.STR_MAGIC_RET, fun.return_type_place, f"magic function '__str__' should return {types.STR}, not {fun.return_type}")
			if fun.name == '__init__':
				if rt != types.VOID:
					self.config.errors.critical_error(ET.INIT_MAGIC_RET, fun.return_type_place, f"'__init__' magic method should return '{types.VOID}', not '{fun.return_type}'")
			self.check_fun(fun, semantic_type=SemanticTokenType.BOUND_FUNCTION)
		for static_var in node.static_variables:
			if self.semantic:
				self.semantic_tokens.add(SemanticToken(static_var.var.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,SemanticTokenModifier.STATIC)))
			value = self.check(static_var.value)
			if self.check(static_var.var.typ) != value:
				self.config.errors.add_error(ET.STRUCT_STATICS, static_var.place, f"static variable '{static_var.var.name.operand}' has type '{static_var.var.typ}' but is assigned a value of type '{value}'")
		return types.VOID
	def check_mix(self, node:nodes.Mix) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.FUNCTION, (SemanticTokenModifier.DEFINITION,)))
		return types.VOID
	def check_use(self, node:nodes.Use) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.FUNCTION, (SemanticTokenModifier.DECLARATION,)))
			if node.as_name is not node.name:
				self.semantic_tokens.add(SemanticToken(node.as_name.place,SemanticTokenType.FUNCTION))
		return types.VOID
	def check_return(self, node:nodes.Return) -> Type:
		ret = self.check(node.value)
		if ret != self.expected_return_type:
			self.config.errors.critical_error(ET.RETURN, node.place, f"actual return type '{ret}' does not match specified return type '{self.expected_return_type}'")
		return ret
	def check_dot(self, node:nodes.Dot) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.access.place,SemanticTokenType.PROPERTY))
		origin = self.check(node.origin)
		if isinstance(origin, types.Module):
			typ = self.modules[origin.module.uid].names.get(node.access.operand)
			if typ is None:
				self.config.errors.critical_error(ET.DOT_MODULE, node.access.place, f"name '{node.access}' was not found in module '{origin.path}'")
			return typ
		if isinstance(origin, types.StructKind):
			_, ty = node.lookup_struct_kind(origin, self.config)
			return self.check(ty)
		if isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Struct):
				k = node.lookup_struct(pointed.struct, self.config)
				if isinstance(k,tuple):
					return types.Ptr(self.check(k[1]))
				return types.BoundFun(k.typ(self.check),origin,'')
		self.config.errors.critical_error(ET.DOT, node.access.place, f"'{origin}' object doesn't have any attributes")
	def check_get_item(self, node:nodes.Subscript) -> Type:
		origin = self.check(node.origin)
		subscripts = [self.check(subscript) for subscript in node.subscripts]
		if origin == types.STR:
			if len(subscripts) != 1:
				self.config.errors.critical_error(ET.STR_SUBSCRIPT_LEN, node.access_place, f"string subscripts should have 1 argument, not {len(subscripts)}")
			if subscripts[0] != types.INT:
				self.config.errors.add_error(ET.STR_SUBSCRIPT, node.access_place, f"string subscript should be 1 '{types.INT}' not '{subscripts[0]}'")
			return types.CHAR
		if isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Array):
				if len(subscripts) != 1:
					self.config.errors.critical_error(ET.ARRAY_SUBSCRIPT_LEN, node.access_place, f"array subscripts should have 1 argument, not {len(subscripts)}")
				if subscripts[0] != types.INT:
					self.config.errors.add_error(ET.ARRAY_SUBSCRIPT, node.access_place, f"array subscript should be '{types.INT}' not '{subscripts[0]}'")
				return types.Ptr(pointed.typ)
			if isinstance(pointed, types.Struct):
				fun_node = pointed.struct.get_magic('subscript')
				if fun_node is None:
					self.config.errors.critical_error(ET.SUBSCRIPT_MAGIC, node.access_place, f"structure '{pointed.name}' does not have __subscript__ magic defined")
				fun = fun_node.typ(self.check)
				if len(subscripts) != len(fun.arg_types)-1:
					self.config.errors.critical_error(ET.STRUCT_SUB_LEN, node.access_place, f"'{pointed}' struct subscript should have {len(fun.arg_types)} arguments, not {len(subscripts)}")
				for idx, subscript in enumerate(subscripts):
					if fun.arg_types[idx+1] != subscript:
						self.config.errors.add_error(ET.STRUCT_SUBSCRIPT, node.access_place, f"invalid subscript argument {idx} '{subscript}' for '{pointed}', expected type '{fun.arg_types[idx+1]}''")
				return fun.return_type
		self.config.errors.critical_error(ET.SUBSCRIPT, node.access_place, f"'{origin}' object is not subscriptable")
	def check_template(self, node:nodes.Template) -> Type:
		for val in node.values:
			self.check(val)
		if node.formatter is None:
			formatter = self.names.get(DEFAULT_TEMPLATE_STRING_FORMATTER)
			assert formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER was not imported from sys.builtin"
		else:
			formatter = self.check(node.formatter)
		if isinstance(formatter, types.BoundFun):
			formatter = formatter.apparent_typ
		if not isinstance(formatter, types.Fun):
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.critical_error(ET.TEMPLATE_FUN, node.formatter.place, f"template formatter should be a function, not '{formatter}'")
		if len(formatter.arg_types) != 3:
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.critical_error(ET.TEMPLATE_ARGS, node.formatter.place, f"template formatter should have 3 arguments, not {len(formatter.arg_types)}")
		if formatter.arg_types[0] != types.Ptr(types.Array(types.STR)):#*[]str
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.add_error(ET.TEMPLATE_ARG0, node.formatter.place, f"template formatter argument 0 (strings) should be '{types.Ptr(types.Array(types.STR))}', not '{formatter.arg_types[0]}'")
		if formatter.arg_types[1] != types.Ptr(types.Array(types.STR)):#*[]str
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.add_error(ET.TEMPLATE_ARG1, node.formatter.place, f"template formatter argument 1 (values) should be '{types.Ptr(types.Array(types.STR))}', not '{formatter.arg_types[1]}'")
		if formatter.arg_types[2] != types.INT:#int
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.add_error(ET.TEMPLATE_ARG2, node.formatter.place, f"template formatter argument 2 (length) should be '{types.INT}', not '{formatter.arg_types[2]}'")
		return formatter.return_type
	def check_string_cast(self, node:nodes.StrCast) -> Type:
		# length should be int, pointer should be ptr(*[]char)
		length = self.check(node.length)
		if length != types.INT:
			self.config.errors.add_error(ET.STR_CAST_LEN, node.place, f"string length should be '{types.INT}' not '{length}'")
		pointer = self.check(node.pointer)
		if pointer != types.Ptr(types.Array(types.CHAR)):
			self.config.errors.add_error(ET.STR_CAST_PTR, node.place, f"string pointer should be '{types.Ptr(types.Array(types.CHAR))}' not '{pointer}'")
		return types.STR
	def check_cast(self, node:nodes.Cast) -> Type:
		left = self.check(node.value)
		right = self.check(node.typ)
		isptr:Callable[[Type], bool] = lambda typ: isinstance(typ, types.Ptr)
		if not (
			(isptr(left) and isptr(right)) or
			(left == types.STR   and right == types.Ptr(types.Array(types.CHAR))) or
			(left == types.STR   and right == types.INT  ) or
			(left == types.BOOL  and right == types.CHAR ) or
			(left == types.BOOL  and right == types.SHORT) or
			(left == types.BOOL  and right == types.INT  ) or
			(left == types.CHAR  and right == types.SHORT) or
			(left == types.CHAR  and right == types.INT  ) or
			(left == types.SHORT and right == types.INT  ) or
			(left == types.INT   and right == types.SHORT) or
			(left == types.INT   and right == types.CHAR ) or
			(left == types.INT   and right == types.BOOL ) or
			(left == types.SHORT and right == types.CHAR ) or
			(left == types.SHORT and right == types.BOOL ) or
			(left == types.CHAR  and right == types.BOOL )
		):
			self.config.errors.critical_error(ET.CAST, node.place, f"casting type '{left}' to type '{right}' is not supported")
		return right
	def check_type_pointer(self, node:nodes.TypePointer) -> Type:
		pointed = self.check(node.pointed)
		return types.Ptr(pointed)
	def check_type_array(self, node:nodes.TypeArray) -> Type:
		element = self.check(node.typ)
		return types.Array(element, node.size)
	def check_type_fun(self, node:nodes.TypeFun) -> Type:
		args = tuple(self.check(arg) for arg in node.args)
		return_type:Type = types.VOID
		if node.return_type is not None:
			return_type = self.check(node.return_type)
		return types.Fun(args, return_type)
	def check_type_reference(self, node:nodes.TypeReference) -> Type:
		name = node.ref.operand
		if name == 'void': return types.VOID
		if name == 'bool': return types.BOOL
		if name == 'char': return types.CHAR
		if name == 'short': return types.SHORT
		if name == 'int': return types.INT
		if name == 'str': return types.STR
		assert len(types.Primitive) == 6, "Exhaustive check of Primitives, (implement next primitive type here)"
		typ = self.type_names.get(name)
		if typ is None:
			self.config.errors.critical_error(ET.TYPE_REFERENCE, node.ref.place, f"type '{name}' is not defined")
		return typ
	def check(self, node:Node) -> Type:
		if   type(node) == nodes.Import           : return self.check_import         (node)
		elif type(node) == nodes.FromImport       : return self.check_from_import    (node)
		elif type(node) == nodes.Fun              : return self.check_fun            (node)
		elif type(node) == nodes.Var              : return self.check_var            (node)
		elif type(node) == nodes.Const            : return self.check_const          (node)
		elif type(node) == nodes.Mix              : return self.check_mix            (node)
		elif type(node) == nodes.Struct           : return self.check_struct         (node)
		elif type(node) == nodes.Code             : return self.check_code           (node)
		elif type(node) == nodes.Call             : return self.check_call           (node)
		elif type(node) == nodes.BinaryExpression : return self.check_bin_exp        (node)
		elif type(node) == nodes.UnaryExpression  : return self.check_unary_exp      (node)
		elif type(node) == nodes.Constant         : return self.check_constant       (node)
		elif type(node) == nodes.ExprStatement    : return self.check_expr_state     (node)
		elif type(node) == nodes.Assignment       : return self.check_assignment     (node)
		elif type(node) == nodes.ReferTo          : return self.check_refer          (node)
		elif type(node) == nodes.Declaration      : return self.check_declaration    (node)
		elif type(node) == nodes.Save             : return self.check_save           (node)
		elif type(node) == nodes.VariableSave     : return self.check_variable_save  (node)
		elif type(node) == nodes.If               : return self.check_if             (node)
		elif type(node) == nodes.While            : return self.check_while          (node)
		elif type(node) == nodes.Set              : return self.check_set            (node)
		elif type(node) == nodes.Return           : return self.check_return         (node)
		elif type(node) == nodes.Dot              : return self.check_dot            (node)
		elif type(node) == nodes.Subscript        : return self.check_get_item       (node)
		elif type(node) == nodes.Cast             : return self.check_cast           (node)
		elif type(node) == nodes.StrCast          : return self.check_string_cast    (node)
		elif type(node) == nodes.Use              : return self.check_use            (node)
		elif type(node) == nodes.Str              : return self.check_str            (node)
		elif type(node) == nodes.Int              : return self.check_int            (node)
		elif type(node) == nodes.Short            : return self.check_short          (node)
		elif type(node) == nodes.CharStr          : return self.check_char_str       (node)
		elif type(node) == nodes.CharNum          : return self.check_char_num       (node)
		elif type(node) == nodes.Template         : return self.check_template       (node)
		elif type(node) == nodes.TypePointer      : return self.check_type_pointer   (node)
		elif type(node) == nodes.TypeArray        : return self.check_type_array     (node)
		elif type(node) == nodes.TypeFun          : return self.check_type_fun       (node)
		elif type(node) == nodes.TypeReference    : return self.check_type_reference (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
