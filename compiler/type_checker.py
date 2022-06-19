from typing import Callable

from .primitives import nodes, Node, ET, Config, Type, types, NotSaveableException, DEFAULT_TEMPLATE_STRING_FORMATTER, BUILTIN_WORDS, Place



class type_check:
	__slots__ = ('config', 'module', 'modules', 'names', 'structs', 'expected_return_type')
	def __init__(self, module:nodes.Module, config:Config) -> None:
		self.module = module
		self.config = config
		self.names:dict[str, Type] = {}
		self.structs:dict[str,nodes.Struct] = {}
		self.modules:dict[int, type_check] = {}
		self.expected_return_type:Type = types.VOID

		if module.builtin_module is not None:
			tc = type_check(module.builtin_module, self.config)
			self.modules[module.builtin_module.uid] = tc
			for name in BUILTIN_WORDS:
				typ = tc.names.get(name)
				assert typ is not None, f"Unreachable, std.builtin does not have word '{name}' defined, but it must"
				self.names[name] = tc.names[name]
				if isinstance(typ, types.StructKind):
					struct = tc.structs.get(name)
					if struct is not None:
						self.structs[name] = struct
						continue

		for top in module.tops:
			if isinstance(top,nodes.Import):
				self.names[top.name] = types.Module(top.module)
				self.modules[top.module.uid] = type_check(top.module, self.config)
			elif isinstance(top,nodes.FromImport):
				tc = type_check(top.module, self.config)
				self.modules[top.module.uid] = tc
				for name in top.imported_names:
					typ = tc.names.get(name)
					if typ is not None:
						self.names[name] = tc.names[name]
						if isinstance(typ, types.StructKind):
							struct = tc.structs.get(name)
							if struct is not None:
								self.structs[name] = struct
								continue
						continue
					self.config.errors.add_error(ET.IMPORT_NAME, top.place, f"name '{name}' is not defined in module '{top.module.path}'")
			elif isinstance(top,nodes.Var):
				self.names[top.name.operand] = types.Ptr(top.typ)
			elif isinstance(top,nodes.Const):
				self.names[top.name.operand] = types.INT
			elif isinstance(top, nodes.Mix):
				self.names[top.name.operand] = types.Mix(tuple(self.check(fun_ref) for fun_ref in top.funs),top.name.operand)
			elif isinstance(top,nodes.Use):
				self.names[top.name.operand] = types.Fun(top.arg_types,top.return_type)
			elif isinstance(top,nodes.Fun):
				self.names[top.name.operand] = types.Fun(tuple(arg.typ for arg in top.arg_types), top.return_type)
				if top.name.operand == 'main':
					if top.return_type != types.VOID:
						self.config.errors.add_error(ET.MAIN_RETURN, top.return_type_place, f"entry point (function 'main') has to return {types.VOID}, found '{top.return_type}'")
					if len(top.arg_types) != 0:
						self.config.errors.add_error(ET.MAIN_ARGS, top.args_place, f"entry point (function 'main') has to take no arguments, found '({', '.join(map(str,top.arg_types))})'")
			elif isinstance(top,nodes.Struct):
				self.structs[top.name.operand] = top
				self.names[top.name.operand] = types.StructKind(top)

		for top in module.tops:
			self.check(top)
	def check_import(self, node:nodes.Import) -> Type:
		return types.VOID
	def check_from_import(self, node:nodes.FromImport) -> Type:
		return types.VOID
	def check_fun(self, node:nodes.Fun) -> Type:
		vars_before = self.names.copy()
		self.names.update({arg.name.operand:arg.typ for arg in node.arg_types})
		self.expected_return_type = node.return_type
		ret_typ = self.check(node.code)
		if node.return_type != ret_typ:
			self.config.errors.add_error(ET.FUN_RETURN, node.return_type_place, f"specified return type '{node.return_type}' does not match actual return type '{ret_typ}'")
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
					magic.typ.arg_types[1:],
					types.Ptr(types.Struct(called.name))
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
		right = self.check(node.right)
		return node.typ(left,right, self.config)
	def check_expr_state(self, node:nodes.ExprStatement) -> Type:
		self.check(node.value)
		return types.VOID
	def check_str(self, node:nodes.Str) -> Type:
		return types.STR
	def check_int(self, node:nodes.Int) -> Type:
		return types.INT
	def check_short(self, node:nodes.Short) -> Type:
		return types.SHORT
	def check_char(self, node:nodes.Char) -> Type:
		return types.CHAR
	def check_assignment(self, node:nodes.Assignment) -> Type:
		actual_type = self.check(node.value)
		if node.var.typ != actual_type:
			self.config.errors.add_error(ET.ASSIGNMENT, node.place, f"specified type '{node.var.typ}' does not match actual type '{actual_type}' in assignment")
		self.names[node.var.name.operand] = types.Ptr(node.var.typ)
		return types.VOID
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.names.get(node.name.operand)
		if typ is None:
			self.config.errors.critical_error(ET.REFER, node.place, f"did not find name '{node.name}'")
		return typ
	def check_declaration(self, node:nodes.Declaration) -> Type:
		if node.times is None:
			self.names[node.var.name.operand] = types.Ptr(node.var.typ)
			return types.VOID
		times = self.check(node.times)
		if times != types.INT:
			self.config.errors.add_error(ET.DECLARATION_TIMES, node.place, f"number of elements to allocate should be an '{types.INT}', got '{times}'")
		self.names[node.var.name.operand] = types.Ptr(types.Array(node.var.typ))
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
			self.config.errors.add_error(ET.IF, node.place, f"if statement expected '{types.BOOL}' type, got '{actual}'")
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
		value = self.check(node.value)
		self.names[node.name.operand] = value
		return types.VOID
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		return node.typ(self.check(node.left), self.config)
	def check_constant(self, node:nodes.Constant) -> Type:
		return node.typ
	def check_var(self, node:nodes.Var) -> Type:
		return types.VOID
	def check_const(self, node:nodes.Const) -> Type:
		return types.VOID
	def check_struct(self, node:nodes.Struct) -> Type:
		for fun in node.funs:
			self_should_be = types.Ptr(types.Struct(node.name.operand))
			if len(fun.arg_types)==0:
				self.config.errors.critical_error(ET.STRUCT_FUN_ARGS, fun.args_place, f"bound function's argument 0 should be '{self_should_be}' (self), found 0 arguments")
			elif fun.arg_types[0].typ != self_should_be:
				self.config.errors.add_error(ET.STRUCT_FUN_ARG, fun.arg_types[0].place, f"bound function's argument 0 should be '{self_should_be}' (self) got '{fun.arg_types[0].typ}'")
			if fun.name == '__str__':
				if len(fun.arg_types) != 1:
					self.config.errors.critical_error(ET.STR_MAGIC, fun.args_place, f"magic function '__str__' should have 1 argument, not {len(fun.arg_types)}")
				if fun.return_type != types.STR:
					self.config.errors.critical_error(ET.STR_MAGIC_RET, fun.return_type_place, f"magic function '__str__' should return {types.STR}, not {fun.return_type}")
			if fun.name == '__init__':
				if fun.return_type != types.VOID:
					self.config.errors.critical_error(ET.INIT_MAGIC_RET, fun.return_type_place, f"'__init__' magic method should return '{types.VOID}', not '{fun.return_type}'")
			self.check(fun)
		for var in node.static_variables:
			value = self.check(var.value)
			if var.var.typ != value:
				self.config.errors.add_error(ET.STRUCT_STATICS, var.place, f"static variable '{var.var.name.operand}' has type '{var.var.typ}' but is assigned a value of type '{value}'")
		return types.VOID
	def check_mix(self, node:nodes.Mix) -> Type:
		return types.VOID
	def check_use(self, node:nodes.Use) -> Type:
		return types.VOID
	def check_return(self, node:nodes.Return) -> Type:
		ret = self.check(node.value)
		if ret != self.expected_return_type:
			self.config.errors.critical_error(ET.RETURN, node.place, f"actual return type '{ret}' does not match specified return type '{self.expected_return_type}'")
		return ret
	def check_dot(self, node:nodes.Dot) -> Type:
		origin = self.check(node.origin)
		if isinstance(origin, types.Module):
			typ = self.modules[origin.module.uid].names.get(node.access.operand)
			if typ is None:
				self.config.errors.critical_error(ET.DOT_MODULE, node.access.place, f"name '{node.access}' was not found in module '{origin.path}'")
			return typ
		if isinstance(origin, types.StructKind):
			return node.lookup_struct_kind(origin, self.config)[1]
		if isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Struct):
				struct = self.structs.get(pointed.name)
				if struct is None:
					self.config.errors.critical_error(ET.STRUCT_TYPE_DOT, node.access.place, f"structure '{pointed.name}' does not exist (caught in dot)")
				k = node.lookup_struct(struct, self.config)
				if isinstance(k,tuple):
					return types.Ptr(k[1])
				return types.BoundFun(k.typ,origin,'')
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
				struct = self.structs.get(pointed.name)
				if struct is None:
					self.config.errors.critical_error(ET.STRUCT_TYPE_SUB, node.access_place, f"structure '{pointed.name}' does not exist (caught in subscript)")
				fun_node = struct.get_magic('subscript')
				if fun_node is None:
					self.config.errors.critical_error(ET.SUBSCRIPT_MAGIC, node.access_place, f"structure '{pointed.name}' does not have __subscript__ magic defined")
				fun = fun_node.typ
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
		right = node.typ
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
			self.config.errors.critical_error(ET.CAST, node.place, f"casting type '{left}' to type '{node.typ}' is not supported")
		return node.typ
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
		elif type(node) == nodes.Set            : return self.check_set            (node)
		elif type(node) == nodes.Return           : return self.check_return         (node)
		elif type(node) == nodes.Dot              : return self.check_dot            (node)
		elif type(node) == nodes.Subscript        : return self.check_get_item       (node)
		elif type(node) == nodes.Cast             : return self.check_cast           (node)
		elif type(node) == nodes.StrCast          : return self.check_string_cast    (node)
		elif type(node) == nodes.Use              : return self.check_use            (node)
		elif type(node) == nodes.Str              : return self.check_str            (node)
		elif type(node) == nodes.Int              : return self.check_int            (node)
		elif type(node) == nodes.Short            : return self.check_short          (node)
		elif type(node) == nodes.Char             : return self.check_char           (node)
		elif type(node) == nodes.Template         : return self.check_template       (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
