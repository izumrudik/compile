import math
from typing import Callable

from .primitives import Node, nodes, TT, Config, Type, types, DEFAULT_TEMPLATE_STRING_FORMATTER, INT_TO_STR_CONVERTER, CHAR_TO_STR_CONVERTER, MAIN_MODULE_PATH, BUILTIN_WORDS, STRING_MULTIPLICATION, BOOL_TO_STR_CONVERTER, ASSERT_FAILURE_HANDLER
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

imported_modules:'dict[str,GenerateAssembly]' = {}
class GenerateAssembly:
	__slots__ = ('text','module','config', 'funs', 'names', 'modules', 'type_names', 'insert_before_text', 'text_in_setup')
	def __init__(self, module:nodes.Module, config:Config) -> None:
		self.config             :Config                    = config
		self.module             :nodes.Module              = module
		self.text               :str                       = ''
		self.text_in_setup      :str                       = ''
		self.insert_before_text :str                       = ''
		self.names              :dict[str,TV]              = {}
		self.modules            :dict[int,GenerateAssembly]= {}
		self.type_names         :dict[str,Type]            = {}
		self.generate_assembly()
	def visit_from_import(self,node:nodes.FromImport) -> TV:
		gen = self.import_module(node.module)
		for nam in node.imported_names:
			name = nam.operand
			type_definition = gen.type_names.get(name)
			definition = gen.names.get(name)
			assert type_definition is not None or None is not definition, "type checker broke"
			if definition is not None:
				self.names[name] = definition
			if type_definition is not None:
				self.type_names[name] = type_definition
		return TV()
	def visit_import(self, node:nodes.Import) -> TV:
		self.import_module(node.module)
		self.names[node.name] = TV(types.Module(node.module.uid,node.module.path))
		return TV()
	def visit_fun(self, node:nodes.Fun, name:str|None=None) -> TV:
		if name is None:
			return self.visit_fun(node, node.llvmid)
		self.names[node.name.operand] = TV(node.typ(self.check),node.llvmid)
		old = self.names.copy()
		old_text = self.text
		self.text = ''

		for arg in node.arg_types:
			self.names[arg.name.operand] = TV(self.check(arg.typ),f'%argument{arg.uid}')
		ot = self.check(node.return_type) if node.return_type is not None else types.VOID
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
({', '.join(f'{self.check(arg.typ).llvm} %argument{arg.uid}' for arg in node.arg_types)}) {{
	{f'%return_variable = alloca {ot.llvm}' if ot != types.VOID else ''}
"""
		self.visit(node.code)

		if node.name.operand == 'main':
			self.text += f"""\
	ret i64 0
}}
"""
			self.names = old
			assert node.arg_types == ()
			assert node.return_type is None or self.check(node.return_type) == types.VOID
			return TV()
		self.text += f"""\
	{f'br label %return' if ot == types.VOID else 'unreachable'}
return:
	{f'''%retval = load {ot.llvm}, {ot.llvm}* %return_variable
	ret {ot.llvm} %retval''' if ot != types.VOID else 'ret void'}
}}
"""
		self.names = old
		self.insert_before_text += self.text
		self.text = old_text
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
				m = called.typ.struct.get_magic('init')
				assert m is not None
				magic,llvmid = m
				return types.Fun(
					magic.arg_types[1:],
					types.Ptr(called.typ.struct),
				), called
			if isinstance(called.typ, types.Mix):
				for idx,ref in enumerate(called.typ.funs):
					fun,tv = get_fun_out_of_called(TV(ref,f"extractvalue({called}, {idx})"))
					if len(actual_types) != len(fun.arg_types):
						continue#continue searching
					for actual_arg,arg in zip(actual_types,fun.arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun,tv#found fun
					continue
				assert False
			assert False, f"called is {called}"
		fun_equiv,callable = get_fun_out_of_called(func)
		assert isinstance(callable.typ,types.Fun|types.BoundFun|types.StructKind)
		return_tv = None
		if isinstance(callable.typ,types.BoundFun):
			fun = TV(callable.typ.fun,callable.val)
			args = [TV(callable.typ.typ,callable.typ.val)] + args
		elif isinstance(callable.typ,types.StructKind):
			struct = callable.typ.struct
			m = struct.get_magic('init')
			assert m is not None
			magic, llvmid = m
			return_tv = self.allocate_type_helper(callable.typ.struct, uid)
			fun = TV(magic, llvmid)
			args = [return_tv] + args
		else:
			fun = callable
		assert isinstance(fun.typ,types.Fun)
		
		self.text+=f"""\
	{f'%callresult.{uid} = ' if fun.typ.return_type != types.VOID else ''}call {fun.typ.return_type.llvm} {fun.val}({', '.join(str(a) for a in args)})
"""
		if return_tv is None:
			return_tv = TV(fun.typ.return_type, f"%callresult.{uid}" if fun.typ.return_type != types.VOID else '')
		return return_tv
	def visit_call(self, node:nodes.Call) -> TV:
		args = [self.visit(arg) for arg in node.args]
		return self.call_helper(self.visit(node.func), args, f"actual_call_node.{node.uid}")
	def visit_str(self, node:nodes.Str) -> TV:
		return self.create_str(node.token.operand,f"actual.{node.uid}")
	def create_str(self, s:str, uid:str) -> TV:
		l = len(s)
		string = ''.join('\\'+('0'+hex(ord(c))[2:])[-2:] for c in s)
		uid = self.module.module_couple_llvmid(f"string.{uid}")
		self.insert_before_text += f"{uid} = private constant [{l} x i8] c\"{string}\"\n"

		return TV(types.STR,f"<{{i64 {l}, [0 x i8]* bitcast([{l} x i8]* {uid} to [0 x i8]*)}}>")
	def visit_int(self, node:nodes.Int) -> TV:
		return TV(types.INT, node.token.operand)
	def visit_short(self, node:nodes.Short) -> TV:
		return TV(types.SHORT, node.token.operand)
	def visit_char_str(self, node:nodes.CharStr) -> TV:
		return TV(types.CHAR, f"{ord(node.token.operand)}")
	def visit_char_num(self, node:nodes.CharNum) -> TV:
		return TV(types.CHAR, f"{node.token.operand}")
	def visit_template(self, node:nodes.Template) -> TV:
		strings_array_ptr = self.allocate_type_helper(types.STR, f"template_strings_array.{node.uid}", TV(types.INT, f"{len(node.strings)}"))
		assert isinstance(strings_array_ptr.typ,types.Ptr)
		for idx,va in enumerate(node.strings):
			a = self.create_str(va.operand,f"template_string.{idx}.{node.uid}")
			self.text += f"""\
	%template.strings.{idx}.{node.uid} = getelementptr {strings_array_ptr.typ.pointed.llvm}, {strings_array_ptr}, i32 0, i64 {idx}
	store {a}, {types.Ptr(types.STR).llvm} %template.strings.{idx}.{node.uid}
"""
		values_array_ptr = self.allocate_type_helper(types.STR, f"template_values_array.{node.uid}", TV(types.INT, f"{len(node.strings)}"))
		assert isinstance(values_array_ptr.typ,types.Ptr)
		for idx,val in enumerate(node.values):
			value = self.visit(val)
			typ = value.typ
			a = self.create_str(f"<'{typ}' object>",f"template_value.{idx}.{node.uid}")
			if isinstance(typ,types.Ptr):
				if isinstance(typ.pointed,types.Struct|types.Enum):
					magic_node = typ.pointed.get_magic('str')
					if magic_node is not None:
						fun,llvmid = magic_node
						a = self.call_helper(TV(fun, llvmid), [value], f"template_value_from_magic.{node.uid}")
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
			if typ == types.BOOL:
				converter = self.names.get(BOOL_TO_STR_CONVERTER)
				assert converter is not None, "bool to str converter not found"
				a = self.call_helper(converter, [value], f"template_value_bool.{idx}.{node.uid}")
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
	def visit_bin_exp(self, node:nodes.BinaryOperation) -> TV:
		left = self.visit(node.left)
		right = self.visit(node.right)
		lr = left.typ,right.typ
		lv = left.val
		rv = right.val

		op = node.operation
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
TT.ASTERISK:         f"mul nsw",
TT.DOUBLE_EQUALS:    f"icmp eq",
TT.DOUBLE_GREATER:      f"ashr",
TT.DOUBLE_LESS:          f"shl",
TT.DOUBLE_SLASH:        f"sdiv",
TT.GREATER:         f"icmp sgt",
TT.GREATER_OR_EQUAL:f"icmp sge",
TT.LESS:            f"icmp slt",
TT.LESS_OR_EQUAL:   f"icmp sle",
TT.MINUS:            f"sub nsw",
TT.NOT_EQUALS:       f"icmp ne",
TT.PERCENT:             f"srem",
TT.PLUS:             f"add nsw",
}[node.operation.typ]} {left}, {rv}
"""
		elif (isinstance( left.typ,types.Ptr) and isinstance(right.typ,types.Ptr)):
			self.text += f"""\
	%binary_operation.{node.uid} = { {
TT.DOUBLE_EQUALS: f"icmp eq",
TT.NOT_EQUALS:    f"icmp ne",
}[node.operation.typ] } {left}, {rv}
"""
		elif (isinstance( left.typ,types.Enum) and isinstance(right.typ,types.Enum)):
			self.text += f"""\
	%binary_operation.enum_left.{node.uid} = extractvalue {left}, 0
	%binary_operation.enum_right.{node.uid} = extractvalue {right}, 0
	%binary_operation.{node.uid} = { {
TT.DOUBLE_EQUALS: f"icmp eq",
TT.NOT_EQUALS:    f"icmp ne",
}[node.operation.typ] } {left.typ.llvm_item_id} %binary_operation.enum_left.{node.uid}, %binary_operation.enum_right.{node.uid}
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
		self.names[node.var.name.operand] = self.allocate_type_helper(self.check(node.var.typ),f"declaration.{node.uid}", time)
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
	br label %if_exit_branch.{node.uid}
if_false_branch.{node.uid}:
"""
		if node.else_code is not None:
			self.visit(node.else_code)
		self.text+=f"""\
	br label %if_exit_branch.{node.uid}
if_exit_branch.{node.uid}:
"""
		return TV()
	def visit_while(self, node:nodes.While) -> TV:
		self.text+=f"""\
	br label %while_condition.{node.uid}
while_condition.{node.uid}:
"""
		cond = self.visit(node.condition)
		self.text+=f"""\
	br {cond}, label %while_body.{node.uid}, label %while_exit_branch.{node.uid}
while_body.{node.uid}:
"""
		self.visit(node.code)
		self.text+=f"""\
	br label %while_condition.{node.uid}
while_exit_branch.{node.uid}:
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
		self.names[node.name.operand] = TV(types.Ptr(self.check(node.typ)),f'@{node.name.operand}')
		self.insert_before_text += f"@{node.name.operand} = private global {self.check(node.typ).llvm} undef\n"
		return TV()
	def visit_const(self, node:nodes.Const) -> TV:
		self.names[node.name.operand] = TV(types.INT,f"{node.value}")
		return TV()
	def visit_struct(self, node:nodes.Struct) -> TV:
		struct = types.Struct('',(),0,())
		self.type_names[node.name.operand] = struct
		actual_s_type = node.to_struct(self.check)
		struct.__dict__ = actual_s_type.__dict__#FIXME
		del actual_s_type

		sk = node.to_struct_kind(self.check)
		self.names[node.name.operand] = TV(sk, sk.llvmid)
		self.insert_before_text += f"""\
	{struct.llvm} = type {{{', '.join(self.check(var.typ).llvm for var in node.variables)}}}
	{sk.llvm} = type {{{', '.join(i.llvm for _,i in sk.statics)}}}
	{sk.llvmid} = private global {sk.llvm} undef
"""
		u = f"{node.uid}"
		old = self.text
		self.text = ''
		for idx,i in enumerate(node.static_variables):
			value=self.visit(i.value)
			self.text+=f'''\
	%"v{u}.{idx+1}" = insertvalue {sk.llvm} {f'%"v{u}.{idx}"' if idx !=0 else 'undef'}, {value}, {idx}
'''
		self.text_in_setup+=self.text
		self.text = old
		if len(node.static_variables) != 0:
			self.text+=f'\tstore {sk.llvm} %"v{u}.{len(node.static_variables)}", {types.Ptr(sk).llvm} {sk.llvmid}\n'

		for fun in node.funs:
			self.visit_fun(fun)
		return TV()
	def visit_mix(self,node:nodes.Mix) -> TV:
		tvs = [self.visit(fun_ref) for fun_ref in node.funs]

		val = f"{{{', '.join(map(str,tvs))}}}"

		self.names[node.name.operand] = TV(types.Mix(tuple(i.typ for i in tvs),node.name.operand),val)
		return TV()
	def visit_use(self,node:nodes.Use) -> TV:
		self.names[node.as_name.operand] = TV(types.Fun(tuple(self.check(arg) for arg in node.arg_types),self.check(node.return_type)),f'@{node.name}')
		self.insert_before_text+=f"declare {self.check(node.return_type).llvm} @{node.name}({', '.join(self.check(arg).llvm for arg in node.arg_types)})\n"
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
			v = self.modules[origin.typ.module_uid].names.get(node.access.operand)
			assert v is not None
			return v
		if isinstance(origin.typ,types.StructKind):
			sk = node.lookup_struct_kind(origin.typ, self.config)
			idx,typ = sk
			self.text += f"""\
	%struct_kind_dot_ptr.{node.uid} = getelementptr {origin.typ.llvm}, {TV(types.Ptr(origin.typ),origin.val)}, i32 0, i32 {idx}
	%struct_kind_dot_result.{node.uid} = load {typ.llvm}, {types.Ptr(typ).llvm} %struct_kind_dot_ptr.{node.uid}
"""
			return TV(typ,f'%struct_kind_dot_result.{node.uid}')
		if isinstance(origin.typ, types.EnumKind):
			idx, typ = node.lookup_enum_kind(origin.typ, self.config)
			if isinstance(typ, types.Fun):
				return TV(typ, origin.typ.llvmid_of_type_function(idx))
			return TV(typ, f"{{{origin.typ.enum.llvm_item_id} {idx}, {origin.typ.enum.llvm_max_item} undef}}")
		assert isinstance(origin.typ,types.Ptr), f'dot lookup is not supported for {origin.typ} yet'
		pointed = origin.typ.pointed
		if isinstance(pointed, types.Struct):
			r = node.lookup_struct(pointed, self.config)
			if isinstance(r[0],int):
				idx,result = r
				self.text += f"""\
	%struct_dot_result{node.uid} = getelementptr {pointed.llvm}, {origin}, i32 0, i32 {idx}
"""
				return TV(types.Ptr(result),f"%struct_dot_result{node.uid}")
			fun,llvmid = r
			return TV(types.BoundFun(fun, origin.typ, origin.val), llvmid)
		if isinstance(pointed, types.Enum):
			fun,llvmid = node.lookup_enum(pointed, self.config)
			return TV(types.BoundFun(fun, origin.typ, origin.val), llvmid)
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
			fun = pointed.get_magic('subscript')
			assert fun is not None, "no subscript magic"
			magic,llvmid = fun
			return self.call_helper(TV(magic, llvmid), [origin]+subscripts, f"struct_subscript_result.{node.uid}")
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
		nt = self.check(node.typ)
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
	def visit_enum(self, node:nodes.Enum) -> TV:
		enum = types.Enum('',(),(),(),0)
		self.type_names[node.name.operand] = enum
		actual_enum_type = node.to_enum(self.check)
		enum.__dict__ = actual_enum_type.__dict__#FIXME
		del actual_enum_type
		ek = node.to_enum_kind(self.check)
		self.names[node.name.operand] = TV(ek)
		
		length = len(enum.items)+len(enum.typed_items)
		bits = math.ceil(math.log2(length)) if length != 0 else 1
		#FIXME: find a typ that is maximum of the size and use him as 2nd typ (instead of struct of all types)
		self.insert_before_text += f"""\
	{enum.llvm_item_id} = type i{bits}
	{enum.llvm_max_item} = type {{{', '.join(typ.llvm for name,typ in enum.typed_items)}}}
	{enum.llvm} = type {{{enum.llvm_item_id}, {enum.llvm_max_item}}}
"""
		for idx, (name, ty) in enumerate(enum.typed_items):
			self.insert_before_text += f"""\
define private {enum.llvm} {ek.llvmid_of_type_function(idx)}({ty.llvm} %0) {{
	%2 = alloca {enum.llvm_max_item}
	store {enum.llvm_max_item} zeroinitializer, {enum.llvm_max_item}* %2
	%3 = bitcast {enum.llvm_max_item}* %2 to {ty.llvm}*
	store {ty.llvm} %0, {ty.llvm}* %3
	%4 = load {enum.llvm_max_item}, {enum.llvm_max_item}* %2
	%5 = insertvalue {enum.llvm} undef, {enum.llvm_item_id} {idx}, 0
	%6 = insertvalue {enum.llvm} %5, {enum.llvm_max_item} %4, 1
	ret {enum.llvm} %6
}}
"""
		for fun in node.funs:
			self.visit(fun)
		return TV()
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
		if name == 'bool': return types.BOOL
		if name == 'char': return types.CHAR
		if name == 'int': return types.INT
		if name == 'short': return types.SHORT
		if name == 'str': return types.STR
		if name == 'void': return types.VOID
		assert len(types.Primitive) == 6, "Exhaustive check of Primitives, (implement next primitive type here)"
		typ = self.type_names.get(name)
		assert typ is not None
		return typ
	def check(self, node:Node) -> Type:
		if type(node) == nodes.TypeArray        : return self.check_type_array     (node)
		if type(node) == nodes.TypeFun          : return self.check_type_fun       (node)
		if type(node) == nodes.TypePointer      : return self.check_type_pointer   (node)
		if type(node) == nodes.TypeReference    : return self.check_type_reference (node)
		assert False, f"Unreachable, unknown type {type(node)=}"
	def visit_type_definition(self, node:nodes.TypeDefinition) -> TV:
		self.type_names[node.name.operand] = self.check(node.typ)
		return TV()
	def visit_assert(self, node:nodes.Assert) -> TV:
		value = self.visit(node.value)
		explanation = self.visit(node.explanation)
		if self.config.assume_assert:
			self.text+=f"""\
	call void @llvm.assume({value})
"""
			return TV()
		self.text+=f"""\
	br {value}, label %assert_true.{node.uid}, label %assert_false.{node.uid}
assert_false.{node.uid}:
"""
		handler = self.names.get(ASSERT_FAILURE_HANDLER)
		assert handler is not None, f"no built-in handler {ASSERT_FAILURE_HANDLER}"
		self.call_helper(handler, [self.create_str(f"{node.place}",f"assert_place.{node.uid}"),explanation], f"assert_call.{node.uid}")
		self.text+=f"""
unreachable
assert_true.{node.uid}:
"""
		return TV()
	def visit_match(self, node:nodes.Match) -> TV:
		value = self.visit(node.value)
		if isinstance(value.typ, types.Enum):
			self.text+=f"""\
	%match.switched.value = extractvalue {value}, 0
	switch {value.typ.llvm_item_id} %match.switched.value, label %match_default_branch.{node.uid} [{' '.join(
		f'{value.typ.llvm_item_id} {node.lookup_enum(value.typ, case, self.config)[0]}, label %match_branch_{case.uid}.{node.uid}' for case in node.cases)}]
"""
			for case in node.cases:
				names_before = self.names.copy()
				_, typ = node.lookup_enum(value.typ, case, self.config)
				self.text+=f"""\
match_branch_{case.uid}.{node.uid}:
	%match.enum.0.{case.uid}.{node.uid} = alloca {value.typ.llvm_max_item}
	%match.enum.1.{case.uid}.{node.uid} = extractvalue {value}, 1
	store {value.typ.llvm_max_item} %match.enum.1.{case.uid}.{node.uid}, {value.typ.llvm_max_item}* %match.enum.0.{case.uid}.{node.uid}
	%match.enum.2.{case.uid}.{node.uid} = bitcast {value.typ.llvm_max_item}* %match.enum.0.{case.uid}.{node.uid} to {types.Ptr(typ).llvm}
	%match.enum.value.{case.uid}.{node.uid} = load {typ.llvm}, {types.Ptr(typ).llvm} %match.enum.2.{case.uid}.{node.uid}
"""
				self.names[node.match_as.operand] = TV(typ, f"%match.enum.value.{case.uid}.{node.uid}")
				self.visit(case.body)
				self.names = names_before
				self.text+=f"""\
	br label %match_exit_branch.{node.uid}
"""
			self.text+=f"""\
match_default_branch.{node.uid}:
"""
			if node.default is not None:
				self.visit(node.default)
			self.text+=f"""\
	br label %match_exit_branch.{node.uid}
match_exit_branch.{node.uid}:
"""
		else:
			assert False, f"match type {value.typ} is no implemented"
		return TV()
	def visit(self, node:Node) -> TV:
		if type(node) == nodes.Assignment       : return self.visit_assignment      (node)
		if type(node) == nodes.BinaryOperation  : return self.visit_bin_exp         (node)
		if type(node) == nodes.Call             : return self.visit_call            (node)
		if type(node) == nodes.Cast             : return self.visit_cast            (node)
		if type(node) == nodes.CharNum          : return self.visit_char_num        (node)
		if type(node) == nodes.CharStr          : return self.visit_char_str        (node)
		if type(node) == nodes.Code             : return self.visit_code            (node)
		if type(node) == nodes.Const            : return self.visit_const           (node)
		if type(node) == nodes.Constant         : return self.visit_constant        (node)
		if type(node) == nodes.Declaration      : return self.visit_declaration     (node)
		if type(node) == nodes.Dot              : return self.visit_dot             (node)
		if type(node) == nodes.Enum             : return self.visit_enum            (node)
		if type(node) == nodes.ExprStatement    : return self.visit_expr_state      (node)
		if type(node) == nodes.FromImport       : return self.visit_from_import     (node)
		if type(node) == nodes.Fun              : return self.visit_fun             (node)
		if type(node) == nodes.If               : return self.visit_if              (node)
		if type(node) == nodes.Import           : return self.visit_import          (node)
		if type(node) == nodes.Int              : return self.visit_int             (node)
		if type(node) == nodes.Match            : return self.visit_match           (node)
		if type(node) == nodes.Mix              : return self.visit_mix             (node)
		if type(node) == nodes.ReferTo          : return self.visit_refer           (node)
		if type(node) == nodes.Return           : return self.visit_return          (node)
		if type(node) == nodes.Save             : return self.visit_save            (node)
		if type(node) == nodes.Set              : return self.visit_set             (node)
		if type(node) == nodes.Short            : return self.visit_short           (node)
		if type(node) == nodes.Str              : return self.visit_str             (node)
		if type(node) == nodes.StrCast          : return self.visit_string_cast     (node)
		if type(node) == nodes.Struct           : return self.visit_struct          (node)
		if type(node) == nodes.Subscript        : return self.visit_subscript       (node)
		if type(node) == nodes.Template         : return self.visit_template        (node)
		if type(node) == nodes.TypeDefinition   : return self.visit_type_definition (node)
		if type(node) == nodes.UnaryExpression  : return self.visit_unary_exp       (node)
		if type(node) == nodes.Use              : return self.visit_use             (node)
		if type(node) == nodes.Var              : return self.visit_var             (node)
		if type(node) == nodes.VariableSave     : return self.visit_variable_save   (node)
		if type(node) == nodes.While            : return self.visit_while           (node)
		if type(node) == nodes.Assert           : return self.visit_assert          (node)
		assert False, f'Unreachable, unknown {type(node)=}'
	def generate_assembly(self) -> None:
		if self.module.builtin_module is not None: # import built-ins
			gen = self.import_module(self.module.builtin_module)
			for name in BUILTIN_WORDS:
				typ = gen.names.get(name)
				type_definition = gen.type_names.get(name)
				definition = gen.names.get(name)
				assert type_definition is not None or None is not definition, f"Unreachable, builtin does not have word '{name}' defined, but it must"
				if definition is not None:
					self.names[name] = definition
				if type_definition is not None:
					self.type_names[name] = type_definition

		for top in self.module.tops:
			self.visit(top)

		self.insert_before_text += f"""\
define private void {self.module.llvmid}() {{
{self.text_in_setup}
	ret void
}}
"""
		if self.module.path == MAIN_MODULE_PATH:
			self.insert_before_text = f"""\
; Assembly generated by jararaca compiler github.com/izumrudik/jararaca
@ARGV = private global {types.Ptr(types.Array(types.Ptr(types.Array(types.CHAR)))).llvm} undef
@ARGC = private global {types.INT.llvm} undef
declare void @GC_init()
declare noalias i8* @GC_malloc(i64 noundef)
declare void @llvm.assume(i1)
{types.STR.llvm} = type <{{ i64, [0 x i8]* }}>
""" + self.insert_before_text
		self.text = self.insert_before_text+self.text


	def import_module(self,module:'nodes.Module') -> 'GenerateAssembly':
		if module.path not in imported_modules:
			self.text_in_setup+= f"\tcall void {module.llvmid}()\n"
			gen = GenerateAssembly(module,self.config)
			self.insert_before_text+=gen.text
			imported_modules[module.path] = gen
		else:
			gen = imported_modules[module.path]
		self.modules[module.uid] = gen
		return gen
