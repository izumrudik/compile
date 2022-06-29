from typing import Callable


from .primitives import Node, nodes, TT, Config, Type, types, DEFAULT_TEMPLATE_STRING_FORMATTER, INT_TO_STR_CONVERTER, CHAR_TO_STR_CONVERTER, MAIN_MODULE_PATH, BUILTIN_WORDS, STRING_MULTIPLICATION
from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class TV:#typed value
	ty:Type|None  = None
	val:str = ''
	@property
	def typ(self) -> Type:
		if self.ty is None:
			raise Exception(f"TV has no type: {self}")
		return self.ty
	def __str__(self) -> str:
		if self.ty is None:
			return f"<None TV>"
		if self.ty is types.VOID:
			return f"{self.typ.llvm} 0"
		return f"{self.typ.llvm} {self.val}"
@dataclass(slots=True, frozen=True)
class MixTypeTv(Type):
	funs:list[TV]
	name:str
	def __str__(self) -> str:
		return f"mixTV({self.name})"
	@property
	def llvm(self) -> str:
		raise Exception(f"Mix type does not make sense in llvm, {self}")

imported_modules_paths:'dict[str,GenerateAssembly]' = {}
class GenerateAssembly:
	__slots__ = ('text','module','config', 'funs', 'strings', 'names', 'modules', 'structs')
	def __init__(self, module:nodes.Module, config:Config) -> None:
		self.config   :Config                    = config
		self.module   :nodes.Module              = module
		self.text     :str                       = ''
		self.strings  :list[str]                 = []
		self.names    :dict[str,TV]              = {}
		self.modules  :dict[int,GenerateAssembly]= {}
		self.structs  :dict[str,nodes.Struct]    = {}
		self.generate_assembly()
	def visit_from_import(self,node:nodes.FromImport) -> TV:
		return TV()
	def visit_import(self, node:nodes.Import) -> TV:
		return TV()
	def visit_fun(self, node:nodes.Fun, name:str|None=None) -> TV:
		if name is None:
			return self.visit_fun(node, node.llvmid)
		old = self.names.copy()
		for arg in node.arg_types:
			self.names[arg.name.operand] = TV(self.visit(arg.typ).typ,f'%argument{arg.uid}')
		ot = self.visit(node.return_type).typ
		if node.name.operand == 'main':
			self.text += f"""
define i64 @main(i32 %0, i8** %1){{;entry point
	call void @GC_init()
	call void {self.module.llvmid}()
	%3 = zext i32 %0 to {types.INT.llvm}
	%4 = bitcast i8** %1 to {types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))).llvm}
	store {types.INT.llvm} %3, {types.Ptr(types.INT).llvm} @ARGC
	store {types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))).llvm} %4, {types.Ptr(types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR))))).llvm} @ARGV
"""
		else:
			self.text += f"""
define private {ot.llvm} {name}\
({', '.join(f'{self.visit(arg.typ).typ.llvm} %argument{arg.uid}' for arg in node.arg_types)}) {{
	%return_variable = alloca {ot.llvm}
"""
		self.visit(node.code)

		if node.name.operand == 'main':
			self.text += f"""\
	ret i64 0
}}
"""
			self.names = old
			assert node.arg_types == ()
			assert self.visit(node.return_type).typ == types.VOID
			return TV()
		self.text += f"""\
	{f'br label %return' if ot == types.VOID else 'unreachable'}
return:
	%retval = load {ot.llvm}, {ot.llvm}* %return_variable
	ret {ot.llvm} %retval
}}
"""
		self.names = old
		return TV()
	def visit_code(self, node:nodes.Code) -> TV:
		name_before = self.names.copy()
		for statement in node.statements:
			self.visit(statement)
		self.names = name_before
		return TV()
	def call_helper(self, func:TV, args:list[TV], uid:str) -> TV:
		actual_types = [arg.typ for arg in args]
		def get_fun_out_of_called(called:TV) -> tuple[types.Fun, TV]:
			if isinstance(called.typ, types.Fun):
				return called.typ,called
			if isinstance(called.typ, types.BoundFun):
				return called.typ.apparent_typ,called
			if isinstance(called.typ, types.StructKind):
				magic = called.typ.struct.get_magic('init')
				assert magic is not None
				return types.Fun(
					tuple(self.visit(arg.typ).typ for arg in magic.arg_types[1:]),
					types.Ptr(types.Struct(called.typ.name))
				), called
			if isinstance(called.typ, MixTypeTv):
				for ref in called.typ.funs:
					fun,tv = get_fun_out_of_called(ref)
					if len(actual_types) != len(fun.arg_types):
						continue#continue searching
					for actual_arg,arg in zip(actual_types,fun.arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun,tv#found fun
					continue
				assert False
			assert False
		fun_equiv,callable = get_fun_out_of_called(func)
		assert isinstance(callable.typ,types.Fun|types.BoundFun|types.StructKind)
		return_tv = None
		if isinstance(callable.typ,types.BoundFun):
			fun = TV(callable.typ.fun,callable.val)
			args = [TV(callable.typ.typ,callable.typ.val)] + args
		elif isinstance(callable.typ,types.StructKind):
			struct = callable.typ.struct
			r = struct.get_magic('init')
			assert r is not None
			return_tv = self.allocate_type_helper(types.Struct(callable.typ.name), uid)
			fun = TV(types.Fun(tuple(self.visit(arg.typ).typ for arg in r.arg_types),self.visit(r.return_type).typ), r.llvmid)
			args = [return_tv] + args
		else:
			fun = callable
		assert isinstance(fun.typ,types.Fun)
		self.text+=f"""\
	%callresult.{uid} = call {fun.typ.return_type.llvm} {fun.val}({', '.join(str(a) for a in args)})
"""
		if return_tv is None:
			return_tv = TV(fun.typ.return_type, f"%callresult.{uid}")
		return return_tv
	def visit_call(self, node:nodes.Call) -> TV:
		args = [self.visit(arg) for arg in node.args]
		return self.call_helper(self.visit(node.func), args, f"actual_call_node.{node.uid}")
	def visit_str(self, node:nodes.Str) -> TV:
		return self.create_str_helper(node.token.operand)
	def create_str_helper(self, s:str) -> TV:
		idx = len(self.strings)
		self.strings.append(s)
		l = len(s)
		return TV(types.STR,f"<{{i64 {l}, [0 x i8]* bitcast([{l} x i8]* {self.module.str_llvmid(idx)} to [0 x i8]*)}}>")
	def visit_int(self, node:nodes.Int) -> TV:
		return TV(types.INT, node.token.operand)
	def visit_short(self, node:nodes.Short) -> TV:
		return TV(types.SHORT, node.token.operand)
	def visit_char_str(self, node:nodes.CharStr) -> TV:
		return TV(types.CHAR, f"{ord(node.token.operand)}")
	def visit_char_num(self, node:nodes.CharNum) -> TV:
		return TV(types.CHAR, f"{node.token.operand}")
	def visit_type_node(self, node:nodes.TypeNode) -> TV:
		return TV(node.typ)
	def visit_template(self, node:nodes.Template) -> TV:
		strings_array_ptr = self.allocate_type_helper(types.STR, f"template_strings_array.{node.uid}", TV(types.INT, f"{len(node.strings)}"))
		assert isinstance(strings_array_ptr.typ,types.Ptr)
		for idx,va in enumerate(node.strings):
			a = self.create_str_helper(va.operand)
			self.text += f"""\
	%template.strings.{idx}.{node.uid} = getelementptr {strings_array_ptr.typ.pointed.llvm}, {strings_array_ptr}, i32 0, i64 {idx}
	store {a}, {types.Ptr(types.STR).llvm} %template.strings.{idx}.{node.uid}
"""
		values_array_ptr = self.allocate_type_helper(types.STR, f"template_values_array.{node.uid}", TV(types.INT, f"{len(node.strings)}"))
		assert isinstance(values_array_ptr.typ,types.Ptr)
		for idx,val in enumerate(node.values):
			value = self.visit(val)
			typ = value.typ
			a = self.create_str_helper(f"<'{typ}' object>")
			if isinstance(typ,types.Ptr):
				if isinstance(typ.pointed,types.Struct):
					struct = self.structs.get(typ.pointed.name)
					assert struct is not None
					magic_node = struct.get_magic('str')
					if magic_node is not None:
						fun = types.Fun(tuple(self.visit(arg.typ).typ for arg in magic_node.arg_types),self.visit(magic_node.return_type).typ)
						a = self.call_helper(TV(fun, magic_node.llvmid), [value], f"template_value_struct.{node.uid}")
			if typ == types.STR:
				a = value
			if typ == types.CHAR:
				converter = self.names.get(CHAR_TO_STR_CONVERTER)
				assert converter is not None, "char to str converter not found"
				a = self.call_helper(converter, [value], f"template_value_char.{idx}.{node.uid}")
			if typ == types.INT:
				converter = self.names.get(INT_TO_STR_CONVERTER)
				assert converter is not None, "int to str converter not found"
				a = self.call_helper(converter, [value], f"template_value_int.{idx}.{node.uid}")
			self.text += f"""\
	%template.values.{idx}.{node.uid} = getelementptr {values_array_ptr.typ.pointed.llvm}, {values_array_ptr}, i32 0, i64 {idx}
	store {a}, {types.Ptr(types.STR).llvm} %template.values.{idx}.{node.uid}
"""
		args = [strings_array_ptr,values_array_ptr,TV(types.INT,f'{len(node.values)}')]
		if node.formatter is not None:
			formatter:TV|None = self.visit(node.formatter)
		else:
			formatter = self.names.get(DEFAULT_TEMPLATE_STRING_FORMATTER)
		assert formatter is not None, 'DEFAULT_TEMPLATE_STRING_FORMATTER was not imported from sys.builtin'
		return self.call_helper(formatter, args, f"template.formatter.{node.uid}")
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> TV:
		left = self.visit(node.left)
		right = self.visit(node.right)
		lr = left.typ,right.typ
		lv = left.val
		rv = right.val

		op = node.operation
		implementation:None|str = None
		if op.equals(TT.KEYWORD,'and') and lr == (types.BOOL,types.BOOL):
			self.text +=f"""\
	%binary_operation.{node.uid} = and {types.BOOL.llvm} {lv}, {rv}
"""
		elif op.equals(TT.KEYWORD,'or' ) and lr == (types.BOOL,types.BOOL):
			self.text +=f"""\
	%binary_operation.{node.uid} = or { types.BOOL.llvm} {lv}, {rv}
"""
		elif op.equals(TT.KEYWORD,'xor') and lr == (types.BOOL,types.BOOL):
			self.text +=f"""\
	%binary_operation.{node.uid} = xor { types.BOOL.llvm} {lv}, {rv}
"""
		elif op == TT.ASTERISK and lr == (types.STR, types.INT):
			provider = self.names.get(STRING_MULTIPLICATION)
			assert provider is not None, "string multiplication was not imported from sys.builtin"
			return self.call_helper(provider, [left,right], f"string_multiplication_binary_operation.{node.uid}")
		elif (
				(left.typ == right.typ == types.INT  ) or 
				(left.typ == right.typ == types.SHORT) or 
				(left.typ == right.typ == types.CHAR )):
			if op.equals(TT.KEYWORD,'xor'):
				self.text +=f"""\
	%binary_operation.{node.uid} = xor {left}, {rv}
"""
			elif op.equals(TT.KEYWORD, 'or'):
				self.text +=f"""\
	%binary_operation.{node.uid} = or {left}, {rv}
"""
			elif op.equals(TT.KEYWORD,'and'):
				self.text +=f"""\
	%binary_operation.{node.uid} = and {left}, {rv}
"""
			else:
				self.text +=f"""\
	%binary_operation.{node.uid} = { {
TT.PERCENT:             f"srem",
TT.PLUS:             f"add nsw",
TT.MINUS:            f"sub nsw",
TT.ASTERISK:         f"mul nsw",
TT.DOUBLE_SLASH:        f"sdiv",
TT.LESS:            f"icmp slt",
TT.LESS_OR_EQUAL:   f"icmp sle",
TT.GREATER:         f"icmp sgt",
TT.GREATER_OR_EQUAL:f"icmp sge",
TT.DOUBLE_EQUALS:    f"icmp eq",
TT.NOT_EQUALS:       f"icmp ne",
TT.DOUBLE_LESS:          f"shl",
TT.DOUBLE_GREATER:      f"ashr",
}[node.operation.typ]} {left}, {rv}
"""
		elif (  isinstance( left.typ,types.Ptr) and
			isinstance(right.typ,types.Ptr) ):
			self.text += f"""\
		%binary_operation.{node.uid} ={ {
TT.DOUBLE_EQUALS: f"icmp eq",
TT.NOT_EQUALS:    f"icmp ne",
}[node.operation.typ] } {left} {rv}
"""
		return TV(node.typ(left.typ, right.typ, self.config), f"%binary_operation.{node.uid}") # return if not already
	def visit_expr_state(self, node:nodes.ExprStatement) -> TV:
		self.visit(node.value)
		return TV()
	def visit_refer(self, node:nodes.ReferTo) -> TV:
		tv = self.names.get(node.name.operand)
		assert tv is not None, f"{node.name.place} name '{node.name.operand}' is not defined (tc is broken) {node}"
		return tv
	def allocate_type_helper(self, typ:types.Type, uid:str, times:TV|None = None) -> TV:
		if times is None:
			tv = TV(types.Ptr(typ), f"%new_variable.{uid}")
			time = TV(types.INT,'1')
		else:
			tv = TV(types.Ptr(types.Array(typ)), f"%new_variable.{uid}")
			time = times
		if typ == types.VOID:
			return tv
		self.text += f"""\
	%size_of_new_variable_as_a_ptr.{uid} = getelementptr {typ.llvm}, {types.Ptr(typ).llvm} null, {time}
	%size_of_new_variable.{uid} = ptrtoint {types.Ptr(typ).llvm} %size_of_new_variable_as_a_ptr.{uid} to i64
	%untyped_ptr_to_new_variable.{uid} = call i8* @GC_malloc(i64 %size_of_new_variable.{uid})
	%new_variable.{uid} = bitcast i8* %untyped_ptr_to_new_variable.{uid} to {tv.typ.llvm}
"""
		return tv
	def visit_declaration(self, node:nodes.Declaration) -> TV:
		time:TV|None = None
		if node.times is not None:
			time = self.visit(node.times)
		self.names[node.var.name.operand] = self.allocate_type_helper(self.visit(node.var.typ).typ,f"declaration.{node.uid}", time)
		return TV()
	def visit_assignment(self, node:nodes.Assignment) -> TV:
		val = self.visit(node.value) # get a value to store
		space = self.allocate_type_helper(val.typ,f"assignment.{node.uid}")
		self.names[node.var.name.operand] = space
		self.store_type_helper(space, val)
		return TV()
	def visit_save(self, node:nodes.Save) -> TV:
		space = self.visit(node.space)
		value = self.visit(node.value)
		self.store_type_helper(space,value)
		return TV()
	def store_type_helper(self, space:TV, value:TV) -> None:
		if space.typ == types.VOID:
			return
		self.text += f"\tstore {value}, {space}\n"
	def visit_variable_save(self, node:nodes.VariableSave) -> TV:
		space = self.names.get(node.space.operand)
		value = self.visit(node.value)
		if space is None:
			space = self.allocate_type_helper(value.typ,f"variable_save.{node.uid}")
			self.names[node.space.operand] = space
		self.store_type_helper(space,value)
		return TV()

	def visit_if(self, node:nodes.If) -> TV:
		cond = self.visit(node.condition)
		self.text+=f"""\
	br {cond}, label %if_true_branch.{node.uid}, label %if_false_branch.{node.uid}
if_true_branch.{node.uid}:
"""
		self.visit(node.code)
		self.text+=f"""\
	br label %if_after_branch.{node.uid}
if_false_branch.{node.uid}:
"""
		if node.else_code is not None:
			self.visit(node.else_code)
		self.text+=f"""\
	br label %if_after_branch.{node.uid}
if_after_branch.{node.uid}:
"""
		return TV()
	def visit_while(self, node:nodes.While) -> TV:
		self.text+=f"""\
	br label %while_condition.{node.uid}
while_condition.{node.uid}:
"""
		cond = self.visit(node.condition)
		self.text+=f"""\
	br {cond}, label %while_body.{node.uid}, label %while_after_branch.{node.uid}
while_body.{node.uid}:
"""
		self.visit(node.code)
		self.text+=f"""\
	br label %while_condition.{node.uid}
while_after_branch.{node.uid}:
"""
		return TV()
	def visit_constant(self, node:nodes.Constant) -> TV:
		constants = {
			'False':TV(types.BOOL,'false'),
			'True' :TV(types.BOOL,'true'),
			'Null' :TV(types.Ptr(types.VOID) ,'null'),
			'Argv' :TV(types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))) ,f'%loaded_argv.{node.uid}'),
			'Argc' :TV(types.INT ,f'%loaded_argc.{node.uid}'),
			'Void' :TV(types.VOID),
		}
		if node.name.operand == 'Argv':
			self.text+=f"""\
	%loaded_argv.{node.uid} = load {types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))).llvm}, {types.Ptr(types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR))))).llvm} @ARGV
"""
		if node.name.operand == 'Argc':
			self.text+=f"""\
	%loaded_argc.{node.uid} = load {types.INT.llvm}, {types.Ptr(types.INT).llvm} @ARGC
"""
		implementation = constants.get(node.name.operand)
		assert implementation is not None, f"Constant {node.name} is not implemented yet"
		return implementation
	def visit_unary_exp(self, node:nodes.UnaryExpression) -> TV:
		val = self.visit(node.left)
		l = val.typ
		op = node.operation
		if   op == TT.NOT: i = f'xor {val}, -1'
		elif op == TT.AT:
			assert isinstance(l,types.Ptr), f"{node} {op.place} {val}"
			if l.pointed == types.VOID:
				return TV(types.VOID)
			i = f'load {node.typ(l, self.config).llvm}, {val}'
		else:
			assert False, f"Unreachable, {op = } and {l = }"
		self.text+=f"""\
	%unary_operation.{node.uid} = {i}
"""
		return TV(node.typ(l, self.config),f"%unary_operation.{node.uid}")
	def visit_var(self, node:nodes.Var) -> TV:
		return TV()
	def visit_const(self, node:nodes.Const) -> TV:
		return TV()
	def visit_struct(self, node:nodes.Struct) -> TV:
		for fun in node.funs:
			self.visit_fun(fun)
		return TV()
	def visit_mix(self,node:nodes.Mix) -> TV:
		return TV()
	def visit_use(self,node:nodes.Use) -> TV:
		return TV()
	def visit_set(self,node:nodes.Set) -> TV:
		value = self.visit(node.value)
		self.names[node.name.operand] = value
		return TV()
	def visit_return(self, node:nodes.Return) -> TV:
		rv = self.visit(node.value)
		if rv.typ != types.VOID:
			self.text += f"""\
	store {rv}, {types.Ptr(rv.typ).llvm} %return_variable
"""
		self.text+= f"	br label %return\n"
		return TV()
	def visit_dot(self, node:nodes.Dot) -> TV:
		origin = self.visit(node.origin)
		if isinstance(origin.typ,types.Module):
			v = self.modules[origin.typ.module.uid].names.get(node.access.operand)
			assert v is not None
			return v
		if isinstance(origin.typ,types.StructKind):
			sk = node.lookup_struct_kind(origin.typ, self.config)
			idx,ty = sk
			typ = self.visit(ty).typ
			self.text += f"""\
	%struct_kind_dot_ptr.{node.uid} = getelementptr {origin.typ.llvm}, {TV(types.Ptr(origin.typ),origin.typ.llvmid)}, i32 0, i32 {idx}
	%struct_kind_dot_result{node.uid} = load {typ.llvm}, {types.Ptr(typ).llvm} %struct_kind_dot_ptr.{node.uid}
"""
			return TV(typ,f'%struct_kind_dot_result{node.uid}')
		assert isinstance(origin.typ,types.Ptr), f'dot lookup is not supported for {origin} yet'
		pointed = origin.typ.pointed
		if isinstance(pointed, types.Struct):
			struct = self.structs[pointed.name]
			r = node.lookup_struct(struct, self.config)
			if isinstance(r,tuple):
				idx,ty = r
				typ = self.visit(ty).typ
				self.text += f"""\
	%struct_dot_result{node.uid} = getelementptr {pointed.llvm}, {origin}, i32 0, i32 {idx}
"""
				return TV(types.Ptr(typ),f"%struct_dot_result{node.uid}")
			return TV(types.BoundFun(types.Fun(tuple(self.visit(arg.typ).typ for arg in r.arg_types), self.visit(r.return_type).typ), origin.typ, origin.val), r.llvmid)
		else:
			assert False, f'unreachable, unknown {type(origin.typ.pointed) = }'
	def visit_subscript(self, node:nodes.Subscript) -> TV:
		origin = self.visit(node.origin)
		subscripts = [self.visit(subscript) for subscript in node.subscripts]
		if origin.typ == types.STR:
			assert len(subscripts) == 1
			assert subscripts[0].typ == types.INT
			self.text += f"""\
	%str_subscript_char_array.{node.uid} = extractvalue {origin}, 1
	%str_subscript_ptr_to_char.{node.uid} = getelementptr {types.Array(types.CHAR).llvm}, {types.Ptr(types.Array(types.CHAR)).llvm} %str_subscript_char_array.{node.uid}, i64 0, {subscripts[0]}
	%str_subscript_result.{node.uid} = load i8, i8* %str_subscript_ptr_to_char.{node.uid}
"""
			return TV(types.CHAR,f"%str_subscript_result.{node.uid}")
		assert isinstance(origin.typ,types.Ptr), "unreachable"
		pointed = origin.typ.pointed
		if isinstance(pointed, types.Array):
			assert len(subscripts) == 1
			assert subscripts[0].typ == types.INT
			self.text +=f"""\
	%array_subscript_result.{node.uid} = getelementptr {pointed.llvm}, {origin}, i32 0, {subscripts[0]}
"""
			return TV(types.Ptr(pointed.typ),f'%array_subscript_result.{node.uid}')
		if isinstance(pointed, types.Struct):
			struct = self.structs.get(pointed.name)
			assert struct is not None
			fun_node = struct.get_magic('subscript')
			assert fun_node is not None, "no subscript magic"
			fun = types.Fun(tuple(self.visit(arg.typ).typ for arg in fun_node.arg_types),self.visit(fun_node.return_type).typ)
			return self.call_helper(TV(fun, fun_node.llvmid), [origin]+subscripts, f"struct_subscript_result.{node.uid}")
		else:
			assert False, 'unreachable'
	def visit_string_cast(self, node:nodes.StrCast) -> TV:
		length = self.visit(node.length)
		pointer = self.visit(node.pointer)
		assert length.typ == types.INT
		assert pointer.typ == types.Ptr(types.Array(types.CHAR))
		self.text += f"""\
	%string_cast_half_baked.{node.uid} = insertvalue {types.STR.llvm} undef, {length}, 0
	%string_cast_result.{node.uid} = insertvalue {types.STR.llvm} %string_cast_half_baked.{node.uid}, {pointer}, 1
"""
		return TV(types.STR,f"%string_cast_result.{node.uid}")
	def visit_cast(self, node:nodes.Cast) -> TV:
		val = self.visit(node.value)
		nt = self.visit(node.typ).typ
		vt = val.typ
		isptr:Callable[[types.Type],bool] = lambda t: isinstance(t,types.Ptr)

		if   (vt,nt)==(types.STR,types.INT):
			self.text += f"\t%cast_str_to_int.{node.uid} = extractvalue {val}, 0\n"
			return TV(nt,f"%cast_str_to_int.{node.uid}")
		elif (vt,nt)==(types.STR,types.Ptr(types.Array(types.CHAR))):
			self.text += f"\t%cast_str_to_ptr.{node.uid} = extractvalue {val}, 1\n"
			return TV(nt,f"%cast_str_to_ptr.{node.uid}")
		elif isptr(vt) and isptr(nt)           :op = 'bitcast'
		elif (vt,nt)==(types.BOOL, types.CHAR ):op = 'sext'
		elif (vt,nt)==(types.BOOL, types.SHORT):op = 'sext'
		elif (vt,nt)==(types.BOOL, types.INT  ):op = 'sext'
		elif (vt,nt)==(types.CHAR, types.SHORT):op = 'sext'
		elif (vt,nt)==(types.CHAR, types.INT  ):op = 'sext'
		elif (vt,nt)==(types.SHORT,types.INT  ):op = 'sext'
		elif (vt,nt)==(types.INT,  types.SHORT):op = 'trunc'
		elif (vt,nt)==(types.INT,  types.CHAR ):op = 'trunc'
		elif (vt,nt)==(types.INT,  types.BOOL ):op = 'trunc'
		elif (vt,nt)==(types.SHORT,types.CHAR ):op = 'trunc'
		elif (vt,nt)==(types.SHORT,types.BOOL ):op = 'trunc'
		elif (vt,nt)==(types.CHAR, types.BOOL ):op = 'trunc'
		else:
			assert False, f"cast {vt} -> {nt} is not implemented yet"
		self.text += f"""\
	%cast_result.{node.uid} = {op} {val} to {nt.llvm}
"""
		return TV(nt,f'%cast_result.{node.uid}')
	def visit(self, node:Node) -> TV:
		if type(node) == nodes.Import           : return self.visit_import          (node)
		if type(node) == nodes.FromImport       : return self.visit_from_import     (node)
		if type(node) == nodes.Fun              : return self.visit_fun             (node)
		if type(node) == nodes.Var              : return self.visit_var             (node)
		if type(node) == nodes.Const            : return self.visit_const           (node)
		if type(node) == nodes.Struct           : return self.visit_struct          (node)
		if type(node) == nodes.Code             : return self.visit_code            (node)
		if type(node) == nodes.Mix              : return self.visit_mix             (node)
		if type(node) == nodes.Use              : return self.visit_use             (node)
		if type(node) == nodes.Call             : return self.visit_call            (node)
		if type(node) == nodes.BinaryExpression : return self.visit_bin_exp         (node)
		if type(node) == nodes.UnaryExpression  : return self.visit_unary_exp       (node)
		if type(node) == nodes.ExprStatement    : return self.visit_expr_state      (node)
		if type(node) == nodes.Assignment       : return self.visit_assignment      (node)
		if type(node) == nodes.ReferTo          : return self.visit_refer           (node)
		if type(node) == nodes.Declaration      : return self.visit_declaration     (node)
		if type(node) == nodes.Save             : return self.visit_save            (node)
		if type(node) == nodes.VariableSave     : return self.visit_variable_save   (node)
		if type(node) == nodes.If               : return self.visit_if              (node)
		if type(node) == nodes.While            : return self.visit_while           (node)
		if type(node) == nodes.Set              : return self.visit_set             (node)
		if type(node) == nodes.Return           : return self.visit_return          (node)
		if type(node) == nodes.Constant         : return self.visit_constant        (node)
		if type(node) == nodes.Dot              : return self.visit_dot             (node)
		if type(node) == nodes.Subscript        : return self.visit_subscript       (node)
		if type(node) == nodes.Cast             : return self.visit_cast            (node)
		if type(node) == nodes.StrCast          : return self.visit_string_cast     (node)
		if type(node) == nodes.Str              : return self.visit_str             (node)
		if type(node) == nodes.Int              : return self.visit_int             (node)
		if type(node) == nodes.Short            : return self.visit_short           (node)
		if type(node) == nodes.CharNum          : return self.visit_char_num        (node)
		if type(node) == nodes.CharStr          : return self.visit_char_str        (node)
		if type(node) == nodes.Template         : return self.visit_template        (node)
		if type(node) == nodes.TypeNode         : return self.visit_type_node       (node)
		assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		setup =''
		self.text = f"""
define private void {self.module.llvmid}() {{
"""
		if self.module.builtin_module is not None:
			if self.module.builtin_module.path not in imported_modules_paths:
				self.text+= f"\tcall void {self.module.builtin_module.llvmid}()\n"
				gen = GenerateAssembly(self.module.builtin_module,self.config)
				setup+=gen.text
				imported_modules_paths[self.module.builtin_module.path] = gen
			else:
				gen = imported_modules_paths[self.module.builtin_module.path]
			self.modules[self.module.builtin_module.uid] = gen
			for name in BUILTIN_WORDS:
				typ = gen.names.get(name)
				if typ is not None:
					self.names[name] = gen.names[name]
					if isinstance(typ.typ,types.StructKind):
						struct = gen.structs.get(name)
						if struct is not None:
							self.structs[name] = struct
		for node in self.module.tops:
			if isinstance(node,nodes.Import):
				if node.module.path not in imported_modules_paths:
					self.text+= f"\tcall void {node.module.llvmid}()\n"
					gen = GenerateAssembly(node.module,self.config)
					setup+=gen.text
					imported_modules_paths[node.module.path] = gen
				else:
					gen = imported_modules_paths[node.module.path]
				self.modules[node.module.uid] = gen
				self.names[node.name] = TV(types.Module(node.module))
			elif isinstance(node,nodes.FromImport):
				if node.module.path not in imported_modules_paths:
					self.text+= f"\tcall void {node.module.llvmid}()\n"
					gen = GenerateAssembly(node.module,self.config)
					setup+=gen.text
					imported_modules_paths[node.module.path] = gen
				else:
					gen = imported_modules_paths[node.module.path]
				self.modules[node.module.uid] = gen
				for nam in node.imported_names:
					name = nam.operand
					typ = gen.names.get(name)
					if typ is not None:
						self.names[name] = gen.names[name]
						if isinstance(typ.typ,types.StructKind):
							struct = gen.structs.get(name)
							if struct is not None:
								self.structs[name] = struct
								continue
						continue
			elif isinstance(node,nodes.Fun):
					self.names[node.name.operand] = TV(types.Fun(tuple(self.visit(arg.typ).typ for arg in node.arg_types),self.visit(node.return_type).typ),node.llvmid)
			elif isinstance(node,nodes.Var):
				self.names[node.name.operand] = TV(types.Ptr(self.visit(node.typ).typ),f'@{node.name.operand}')
				setup += f"@{node.name.operand} = private global {self.visit(node.typ).typ.llvm} undef\n"
			elif isinstance(node,nodes.Const):
				self.names[node.name.operand] = TV(types.INT,f"{node.value}")
			elif isinstance(node,nodes.Struct):
				self.names[node.name.operand] = TV(types.StructKind(node))
				self.structs[node.name.operand] = node
				sk = types.StructKind(node)
				setup += f"""\
	{types.Struct(node.name.operand).llvm} = type {{{', '.join(self.visit(var.typ).typ.llvm for var in node.variables)}}}
	{sk.llvm} = type {{{', '.join(self.visit(i.typ).typ.llvm for i in sk.statics)}}}
	{sk.llvmid} = private global {sk.llvm} undef
"""
				u = f"{node.uid}"
				for idx,i in enumerate(node.static_variables):
					value=self.visit(i.value)
					self.text+=f'''\
		%"v{u}.{idx+1}" = insertvalue {sk.llvm} {f'%"v{u}.{idx}"' if idx !=0 else 'undef'}, {value}, {idx}
'''
				if len(node.static_variables) != 0:
					self.text+=f'\tstore {sk.llvm} %"v{u}.{len(node.static_variables)}", {types.Ptr(sk).llvm} {sk.llvmid}\n'
			elif isinstance(node,nodes.Mix):
				self.names[node.name.operand] = TV(MixTypeTv([self.visit(fun_ref) for fun_ref in node.funs],node.name.operand))
			elif isinstance(node,nodes.Use):
				self.names[node.name.operand] = TV(types.Fun(tuple(self.visit(arg).typ for arg in node.arg_types),self.visit(node.return_type).typ),f'@{node.name}')
				setup+=f"declare {self.visit(node.return_type).typ.llvm} @{node.name}({', '.join(self.visit(arg).typ.llvm for arg in node.arg_types)})\n"
		self.text+="\tret void\n}"
		text = ''
		if self.module.path == MAIN_MODULE_PATH:
			text += f"""\
; Assembly generated by jararaca compiler github.com/izumrudik/jararaca
@ARGV = private global {types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))).llvm} undef
@ARGC = private global {types.INT.llvm} undef
declare void @GC_init()
declare noalias i8* @GC_malloc(i64 noundef)
"""
		for node in self.module.tops:
			self.visit(node)
		for idx, string in enumerate(self.strings):
			l = len(string)
			st = ''.join('\\'+('0'+hex(ord(c))[2:])[-2:] for c in string)
			text += f"{self.module.str_llvmid(idx)} = private constant [{l} x i8] c\"{st}\"\n"
		self.text = text+setup+self.text
