from typing import Callable

from .primitives import nodes, Node, ET, add_error, critical_error, Config, Type, types, NotSaveableException



class TypeCheck:
	__slots__ = ('config', 'module', 'modules', 'names', 'structs', 'expected_return_type')
	def __init__(self, module:nodes.Module, config:Config) -> None:
		self.module = module
		self.config = config
		self.names:dict[str, Type] = {}
		self.structs:dict[str,nodes.Struct] = {}
		self.modules:dict[int, TypeCheck] = {}
		self.expected_return_type:Type = types.VOID
		for top in module.tops:
			if isinstance(top,nodes.Import):
				self.names[top.name] = types.Module(top.module)
				self.modules[top.module.uid] = TypeCheck(top.module, self.config)
			elif isinstance(top,nodes.FromImport):
				tc = TypeCheck(top.module, self.config)
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
					add_error(ET.IMPORT_NAME, top.loc, f"name '{name}' is not defined in module '{top.module.path}'")
			elif isinstance(top,nodes.Const):
				self.names[top.name.operand] = types.INT
			elif isinstance(top, nodes.Mix):
				self.names[top.name.operand] = types.Mix(tuple(self.check(fun_ref) for fun_ref in top.funs),top.name.operand)
			elif isinstance(top,nodes.Use):
				self.names[top.name.operand] = types.Fun(top.arg_types,top.return_type)
			elif isinstance(top,nodes.Fun):
				if len(top.generics) != 0:
					self.names[top.name.operand] = types.GenericFun(top)
				else:
					self.names[top.name.operand] = types.Fun(tuple(arg.typ for arg in top.arg_types), top.return_type)
				if top.name.operand == 'main':
					if top.return_type != types.VOID:
						add_error(ET.MAIN_RETURN, top.name.loc, f"entry point (function 'main') has to return nothing, found '{top.return_type}'")
					if len(top.arg_types) != 0:
						add_error(ET.MAIN_ARGS, top.name.loc, f"entry point (function 'main') has to take no arguments, found '{top.arg_types}'")
					if len(top.generics) != 0:
						critical_error(ET.MAIN_GENERIC, top.name.loc, f"entry point (function 'main') cannot be generic")
			elif isinstance(top,nodes.Struct):
				self.structs[top.name.operand] = top
				self.names[top.name.operand] = types.StructKind(top, top.generics)

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
			add_error(ET.FUN_RETURN, node.name.loc, f"specified return type '{node.return_type}' does not match actual return type '{ret_typ}'")
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
			self.check(statement)
		self.names = vars_before #this is scoping
		if ret is None:
			return types.VOID
		return self.expected_return_type
	def check_call(self, node:nodes.Call) -> Type:
		actual_types = [self.check(arg) for arg in node.args]
		def get_fun_out_of_called(called:Type) -> types.Fun:
			if isinstance(called, types.Fun):
				return called
			if isinstance(called, types.BoundFun):
				return called.apparent_typ
			if isinstance(called, types.StructKind):
				d = {o:called.generics[idx] for idx,o in enumerate(called.struct.generics)}
				return types.Fun(
					called.struct.get_magic('init', node.loc).typ.arg_types[1:],
					types.Ptr(types.Struct(called.name,called.generics,))
				).fill_generic(d)
			if isinstance(called, types.Mix):
				for ref in called.funs:
					fun = get_fun_out_of_called(ref)
					if len(actual_types) != len(fun.arg_types):
						continue#continue searching
					for actual_arg,arg in zip(actual_types,fun.arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun#found fun
					continue
				critical_error(ET.CALL_MIX, node.loc, f"did not find function to match '{tuple(actual_types)!s}' contract in mix '{called}'")
			critical_error(ET.CALLABLE, node.loc, f"'{called}' object is not callable")
		fun = get_fun_out_of_called(self.check(node.func))
		if len(fun.arg_types) != len(actual_types):
			critical_error(ET.CALL_ARGS, node.loc, f"function '{fun}' accepts {len(fun.arg_types)} arguments, provided {len(node.args)} arguments")
		for idx, typ in enumerate(actual_types):
			needed = fun.arg_types[idx]
			if typ != needed:
				add_error(ET.CALL_ARG, node.loc, f"function '{fun}' argument {idx} takes '{needed}', got '{typ}'")
		return fun.return_type
	def check_bin_exp(self, node:nodes.BinaryExpression) -> Type:
		left = self.check(node.left)
		right = self.check(node.right)
		return node.typ(left,right)
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
			add_error(ET.ASSIGNMENT, node.var.name.loc, f"specified type '{node.var.typ}' does not match actual type '{actual_type}' in variable assignment")
		self.names[node.var.name.operand] = types.Ptr(node.var.typ)
		return types.VOID
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.names.get(node.name.operand)
		if typ is None:
			critical_error(ET.REFER, node.name.loc, f"did not find name '{node.name}'")
		for generic in node.generics:
			try:generic.llvm
			except NotSaveableException:
				critical_error(ET.UNSAVEABLE_GENERICS, node.name.loc, f"unsaveable types are not allowed to be filled as generics")
		if isinstance(typ,types.StructKind):
			if len(typ.struct.generics) != len(node.generics):
				critical_error(ET.SK_GENERICS, node.name.loc, f"structkind '{typ.name}' has {len(typ.struct.generics)} generics while {len(node.generics)} were specified")
			typ.struct.generic_fills.add(node.generics)
			d = {o:node.generics[idx] for idx,o in enumerate(typ.struct.generics)}
			return typ.fill_generic(d)
		if isinstance(typ,types.GenericFun):
			if len(typ.fun.generics) != len(node.generics):
				critical_error(ET.FUN_GENERICS, node.name.loc, f"generic fun '{typ.name}' has {len(typ.fun.generics)} generics while {len(node.generics)} were specified")
			typ.fun.generic_fills.add(node.generics)
			d = {o:node.generics[idx] for idx,o in enumerate(typ.fun.generics)}
			return typ.fill_generic(d)
		if len(node.generics) != 0:
			add_error(ET.GENERIC_TYPE, node.name.loc, f"type '{typ}' is not generic")
		return typ
	def check_declaration(self, node:nodes.Declaration) -> Type:
		if node.times is None:
			self.names[node.var.name.operand] = types.Ptr(node.var.typ)
			return types.VOID
		times = self.check(node.times)
		if times != types.INT:
			add_error(ET.DECLARATION_TIMES, node.var.name.loc, f"number of elements to allocate should be an '{types.INT}', got '{times}'")
		self.names[node.var.name.operand] = types.Ptr(types.Array(node.var.typ))
		return types.VOID
	def check_save(self, node:nodes.Save) -> Type:
		space = self.check(node.space)
		value = self.check(node.value)
		if not isinstance(space, types.Ptr):
			critical_error(ET.SAVE_PTR, node.loc, f"expected pointer to save into, got '{space}'")
		if space.pointed != value:
			add_error(ET.SAVE, node.loc, f"space type '{space}' does not match value's type '{value}'")
		return types.VOID
	def check_variable_save(self, node:nodes.VariableSave) -> Type:
		space = self.names.get(node.space.operand)
		value = self.check(node.value)
		if space is None:#auto
			try:value.llvm
			except NotSaveableException:
				add_error(ET.UNSAVEABLE_VSAVE, node.loc, f"type '{value}' is not saveable")
			space = types.Ptr(value)
			self.names[node.space.operand] = space
		if not isinstance(space, types.Ptr):
			critical_error(ET.VSAVE_PTR, node.loc, f"expected pointer to save into, got '{space}'")
		if space.pointed != value:
			add_error(ET.VSAVE, node.loc, f"space type '{space}' does not match value's type '{value}'")
		return types.VOID
	def check_if(self, node:nodes.If) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			add_error(ET.IF, node.loc, f"if statement expected '{types.BOOL}' type, got '{actual}'")
		if node.else_code is None:
			return self.check(node.code)
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code)
		if actual_if != actual_else:
			critical_error(ET.IF_BRANCH, node.loc, f"if branches are inconsistent: one branch returns while other does not (refactor without 'else')")
		return actual_if
	def check_while(self, node:nodes.While) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			add_error(ET.WHILE, node.loc, f"while statement expected '{types.BOOL}' type, got '{actual}'")
		return self.check(node.code)
	def check_set(self, node:nodes.Alias) -> Type:
		value = self.check(node.value)
		self.names[node.name.operand] = value
		return types.VOID
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		return node.typ(self.check(node.left))
	def check_constant(self, node:nodes.Constant) -> Type:
		return node.typ
	def check_const(self, node:nodes.Const) -> Type:
		return types.VOID
	def check_struct(self, node:nodes.Struct) -> Type:
		for generic in node.generics:
			types.Generic.fills[generic] = types.VOID
		for fun in node.funs:
			self_should_be = types.Ptr(types.Struct(node.name.operand,
				tuple(node.generics)
			))
			if fun.arg_types[0].typ != self_should_be:
				add_error(ET.STRUCT_FUN_ARG, fun.name.loc, f"bound function's argument 0 should be '{self_should_be}' (self) got '{fun.arg_types[0].typ}'")
			if len(fun.generics) != 0:
				add_error(ET.STRUCT_FUN_GENERIC, fun.name.loc, f"bound functions can't be generic")
			self.check(fun)
		for var in node.static_variables:
			value = self.check(var.value)
			if var.var.typ != value:
				add_error(ET.STRUCT_STATICS, var.var.name.loc, f"static variable '{var.var.name.operand}' has type '{var.var.typ}' but is assigned a value of type '{value}'")
		for generic in node.generics:
			types.Generic.fills.pop(generic)
		return types.VOID
	def check_mix(self, node:nodes.Mix) -> Type:
		return types.VOID
	def check_use(self, node:nodes.Use) -> Type:
		return types.VOID
	def check_return(self, node:nodes.Return) -> Type:
		ret = self.check(node.value)
		if ret != self.expected_return_type:
			critical_error(ET.RETURN, node.loc, f"actual return type '{ret}' does not match specified return type '{self.expected_return_type}'")
		return ret
	def check_dot(self, node:nodes.Dot) -> Type:
		origin = self.check(node.origin)
		if isinstance(origin, types.Module):
			typ = self.modules[origin.module.uid].names.get(node.access.operand)
			if typ is None:
				critical_error(ET.DOT_MODULE, node.loc, f"name '{node.access}' was not found in module '{origin.path}'")
			return typ
		if isinstance(origin, types.StructKind):
			if len(origin.generics) != len(origin.struct.generics):
				critical_error(ET.DOT_SK_GENERICS, node.loc, f"structkind '{origin.name}' has {len(origin.struct.generics)} generics while {len(origin.generics)} were specified")
			for generic in origin.generics:
				try:generic.llvm
				except NotSaveableException:
					add_error(ET.DOT_SK_UNSAVEABLE, node.loc, f"unsaveable types are not allowed to be filled as generics")
			r = node.lookup_struct_kind(origin)[1]
			origin.struct.generic_fills.add(origin.generics)
			d = {o:origin.generics[idx] for idx,o in enumerate(origin.struct.generics)}
			return r.fill_generic(d)
		if isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Struct):
				struct = self.structs.get(pointed.name)
				if struct is None:
					critical_error(ET.STRUCT_TYPE_DOT, node.loc, f"structure '{pointed.name}' does not exist (caught in dot)")
				if len(pointed.generics) != len(struct.generics):
					critical_error(ET.DOT_STRUCT_GENERICS, node.loc, f"structure '{pointed.name}' has {len(struct.generics)} generics while {len(pointed.generics)} were specified (caught in dot)")
				for generic in pointed.generics:
					try:generic.llvm
					except NotSaveableException:
						add_error(ET.DOT_ST_UNSAVEABLE, node.loc, f"unsaveable types are not allowed to be filled as generics (caught in dot)")
				k = node.lookup_struct(struct)
				struct.generic_fills.add(pointed.generics)
				d = {o:pointed.generics[idx] for idx,o in enumerate(struct.generics)}
				if isinstance(k,tuple):
					return types.Ptr(k[1]).fill_generic(d)
				return types.BoundFun(k.typ,origin,'').fill_generic(d)
		critical_error(ET.DOT, node.loc, f"'{origin}' object doesn't have any attributes")
	def check_get_item(self, node:nodes.Subscript) -> Type:
		origin = self.check(node.origin)
		subscript = self.check(node.subscript)
		if origin == types.STR:
			if subscript != types.INT:
				add_error(ET.STR_SUBSCRIPT, node.loc, f"string subscript should be '{types.INT}' not '{subscript}'")
			return types.CHAR
		if isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Array):
				if subscript != types.INT:
					add_error(ET.ARRAY_SUBSCRIPT, node.loc, f"array subscript should be '{types.INT}' not '{subscript}'")
				return types.Ptr(pointed.typ)
			if isinstance(pointed, types.Struct):
				struct = self.structs.get(pointed.name)
				if struct is None:
					critical_error(ET.STRUCT_TYPE_SUB, node.loc, f"structure '{pointed.name}' does not exist (caught in subscript)")
				fun_node = struct.get_magic('subscript',node.loc)
				d = {o:pointed.generics[idx] for idx,o in enumerate(struct.generics)}
				fun = fun_node.typ.fill_generic(d)
				if len(fun.arg_types) != 2:
					critical_error(ET.SUBSCRIPT_MAGIC, fun_node.name.loc, f"magic function '__subscript__' should have 2 arguments, not {len(fun.arg_types)}")
				if fun.arg_types[1] != subscript:
					add_error(ET.STRUCT_SUBSCRIPT, node.loc, f"invalid subscript type '{subscript}' for '{struct.name}, expected type '{fun.arg_types[1]}''")
				return fun.return_type
		critical_error(ET.SUBSCRIPT, node.loc, f"'{origin}' object is not subscriptable")
	def check_string_cast(self, node:nodes.StrCast) -> Type:
		# length should be int, pointer should be ptr(char)
		length = self.check(node.length)
		if length != types.INT:
			add_error(ET.STR_CAST_LEN, node.loc, f"string length should be '{types.INT}' not '{length}'")
		pointer = self.check(node.pointer)
		if pointer != types.Ptr(types.CHAR):
			add_error(ET.STR_CAST_PTR, node.loc, f"string pointer should be '{types.Ptr(types.CHAR)}' not '{pointer}'")
		return types.STR
	def check_cast(self, node:nodes.Cast) -> Type:
		left = self.check(node.value)
		right = node.typ
		isptr:Callable[[Type], bool] = lambda typ: isinstance(typ, types.Ptr)
		if not (
			(isptr(left) and isptr(right)) or
			(left == types.STR   and isptr(right)        ) or
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
			critical_error(ET.CAST, node.loc, f"casting type '{left}' to type '{node.typ}' is not supported")
		return node.typ
	def check(self, node:Node) -> Type:
		if   type(node) == nodes.Import           : return self.check_import         (node)
		elif type(node) == nodes.FromImport       : return self.check_from_import    (node)
		elif type(node) == nodes.Fun              : return self.check_fun            (node)
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
		elif type(node) == nodes.Alias            : return self.check_set            (node)
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
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
