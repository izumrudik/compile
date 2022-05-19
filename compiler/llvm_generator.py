from typing import Callable
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, id_counter, Type, types
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
		return f"{self.typ.llvm} {self.val}"
@dataclass(slots=True, frozen=True)
class MixTypeTv(Type):
	funs:list[TV]
	name:str
	def __repr__(self) -> str:
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
		self.strings  :list[Token]               = []
		self.names    :dict[str,TV]              = {}
		self.modules  :dict[int,GenerateAssembly]= {}
		self.structs  :dict[str,nodes.Struct]    = {}
		self.generate_assembly()
	def visit_from_import(self,node:nodes.FromImport) -> TV:
		return TV()
	def visit_import(self, node:nodes.Import) -> TV:
		return TV()
	def visit_fun(self, node:nodes.Fun) -> TV:
		old = self.names.copy()

		for arg in node.arg_types:
			self.names[arg.name.operand] = TV(arg.typ,f'%argument{arg.uid}')
		ot = node.return_type
		if node.name.operand == 'main':
			self.text += f"""
define i64 @main(i32 %0, i8** %1){{;entry point
	call void @GC_init()
	call void @setup_{self.module.uid}()
	%3 = zext i32 %0 to {types.INT.llvm}
	%4 = bitcast i8** %1 to {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm}
	store {types.INT.llvm} %3, {types.Ptr(types.INT).llvm} @ARGC
	store {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm} %4, {types.Ptr(types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR))))).llvm} @ARGV
"""
		else:
			self.text += f"""
define private {ot.llvm} {node.llvmid}\
({', '.join(f'{arg.typ.llvm} %argument{arg.uid}' for arg in node.arg_types)}) {{
{f'	%retvar = alloca {ot.llvm}{NEWLINE}' if ot != types.VOID else ''}\
"""
		self.visit(node.code)

		if node.name.operand == 'main':
			self.text += f"""\
	ret i64 0
}}
"""
			self.names = old
			assert node.arg_types == []
			assert node.return_type == types.VOID
			return TV()
		self.text += f"""\
	{f'br label %return' if ot == types.VOID else 'unreachable'}
return:
{f'	%retval = load {ot.llvm}, {ot.llvm}* %retvar{NEWLINE}' if ot != types.VOID else ''}\
	ret {ot.llvm} {'%retval' if ot != types.VOID else ''}
}}
"""
		self.names = old
		return TV()
	def visit_code(self, node:nodes.Code) -> TV:
		name_before = self.names.copy()
		for statemnet in node.statements:
			self.visit(statemnet)
		self.names = name_before
		return TV()
	def visit_call(self, node:nodes.Call) -> TV:
		args = [self.visit(arg) for arg in node.args]
		actual_types = [arg.typ for arg in args]
		def get_fun_out_of_called(called:TV) -> TV:
			if isinstance(called.typ, types.Fun):
				return called
			if isinstance(called.typ,types.BoundFun):
				return called
			if isinstance(called.typ, MixTypeTv):
				for ref in called.typ.funs:
					fun = get_fun_out_of_called(ref)
					assert isinstance(fun.typ,types.Fun), f'python typechecker is not robust enough'
					if len(actual_types) != len(fun.typ.arg_types):
						continue#continue searching
					for actual_arg,arg in zip(actual_types,fun.typ.arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun#found fun
					continue
				assert False, f"ERROR: {node.loc} did not find function to match '{tuple(actual_types)!s}' in mix '{called}'"
			assert False, f"ERROR: {node.loc} '{called}' object is not callable"

		f = get_fun_out_of_called(self.visit(node.func))
		assert isinstance(f.typ,types.Fun|types.BoundFun), f'python typechecker is not robust enough'
		self.text+='\t'
		if isinstance(f.typ,types.BoundFun):
			fun = TV(f.typ.fun.typ,f.val)
			args = [TV(f.typ.typ,f.typ.val)] + args
		else:
			fun = f
		assert isinstance(fun.typ,types.Fun), f'python typechecker is not robust enough'
		if fun.typ.return_type != types.VOID:
			self.text+=f"""\
%callresult{node.uid} = """

		self.text += f"""\
call {fun.typ.return_type.llvm} {fun.val}({', '.join(str(a) for a in args)})
"""
		if fun.typ.return_type != types.VOID:
			return TV(fun.typ.return_type, f"%callresult{node.uid}")
		return TV(types.VOID)
	def visit_token(self, token:Token) -> TV:
		if token.typ == TT.INTEGER:
			return TV(types.INT, token.operand)
		elif token.typ == TT.STRING:
			self.strings.append(token)
			l = len(token.operand)
			u = token.uid
			return TV(types.STR,f"<{{i64 {l}, i8* bitcast([{l} x i8]* @.str.{u} to i8*)}}>")
		elif token.typ == TT.CHARACTER:
			return TV(types.CHAR, f"{ord(token.operand)}")
		elif token.typ == TT.SHORT:
			return TV(types.SHORT, token.operand)
		else:
			assert False, f"Unreachable: {token.typ=}"
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> TV:
		left = self.visit(node.left)
		right = self.visit(node.right)
		lr = left.typ,right.typ
		lv = left.val
		rv = right.val

		op = node.operation
		implementation:None|str = None
		if op.equals(TT.KEYWORD,'and') and lr == (types.BOOL,types.BOOL):
			implementation = f'and {types.BOOL.llvm} {lv}, {rv}'
		elif op.equals(TT.KEYWORD,'or' ) and lr == (types.BOOL,types.BOOL):
			implementation = f'or { types.BOOL.llvm} {lv}, {rv}'
		elif op.equals(TT.KEYWORD,'xor') and lr == (types.BOOL,types.BOOL):
			implementation = f'xor {types.BOOL.llvm} {lv}, {rv}'
		elif (
				(left.typ == right.typ == types.INT  ) or 
				(left.typ == right.typ == types.SHORT) or 
				(left.typ == right.typ == types.CHAR )):
			implementation = {
			TT.PERCENT:             f"srem {left}, {rv}",
			TT.PLUS:                  f"add nsw {left}, {rv}",
			TT.MINUS:                 f"sub nsw {left}, {rv}",
			TT.ASTERISK:              f"mul nsw {left}, {rv}",
			TT.DOUBLE_SLASH:             f"sdiv {left}, {rv}",
			TT.LESS:            f"icmp slt {left}, {rv}",
			TT.LESS_OR_EQUAL:   f"icmp sle {left}, {rv}",
			TT.GREATER:         f"icmp sgt {left}, {rv}",
			TT.GREATER_OR_EQUAL:f"icmp sge {left}, {rv}",
			TT.DOUBLE_EQUALS:    f"icmp eq {left}, {rv}",
			TT.NOT_EQUALS:       f"icmp ne {left}, {rv}",
			TT.DOUBLE_LESS:          f"shl {left}, {rv}",
			TT.DOUBLE_GREATER:      f"ashr {left}, {rv}",
			}.get(node.operation.typ)
			if op.equals(TT.KEYWORD,'xor'):implementation = f'xor {left}, {rv}'
			if op.equals(TT.KEYWORD, 'or'):implementation =  f'or {left}, {rv}'
			if op.equals(TT.KEYWORD,'and'):implementation = f'and {left}, {rv}'
		elif (  isinstance( left.typ,types.Ptr) and
			isinstance(right.typ,types.Ptr) ):
			implementation = {
				TT.DOUBLE_EQUALS:  f"icmp eq {left}, {rv}",
				TT.NOT_EQUALS: f"icmp ne {left}, {rv}",
			}.get(node.operation.typ)
		assert implementation is not None, f"op '{node.operation}' is not implemented yet for {left.typ}, {right.typ} {node.operation.loc}"
		self.text+=f"""\
	%bin_op{node.uid} = {implementation}
"""


		return TV(node.typ(left.typ, right.typ), f"%bin_op{node.uid}")
	def visit_expr_state(self, node:nodes.ExprStatement) -> TV:
		self.visit(node.value)
		return TV()
	def visit_refer(self, node:nodes.ReferTo) -> TV:
		tv = self.names.get(node.name.operand)
		assert tv is not None, f"{node.name.loc} name '{node.name.operand}' is not defined (tc is broken) {node}"
		return tv
	def allocate_type_helper(self, typ:types.Type, uid:int, times:TV|None = None) -> TV:
		if times is None:
			tv = TV(types.Ptr(typ), f"%nv{uid}")
			time = TV(types.INT,'1')
		else:
			tv = TV(types.Ptr(types.Array(0,typ)), f"%nv{uid}")
			time = times
		if typ == types.VOID:
			return tv
		self.text += f"""\
	%tmp1{uid} = getelementptr {typ.llvm}, {types.Ptr(typ).llvm} null, {time}
	%tmp2{uid} = ptrtoint {types.Ptr(typ).llvm} %tmp1{uid} to i64
	%tmp3{uid} = call i8* @GC_malloc(i64 %tmp2{uid})
	%nv{uid} = bitcast i8* %tmp3{uid} to {tv.typ.llvm}
"""
		return tv
	def visit_declaration(self, node:nodes.Declaration) -> TV:
		if node.times is not None:
			time = self.visit(node.times)
		else:
			time = node.times
		self.names[node.var.name.operand] = self.allocate_type_helper(node.var.typ,node.uid, time)
		return TV()
	def visit_assignment(self, node:nodes.Assignment) -> TV:
		val = self.visit(node.value) # get a value to store
		tv = self.allocate_type_helper(val.typ,node.uid)
		self.names[node.var.name.operand] = tv
		if val.typ == types.VOID:
			return TV()
		self.text += f"""\
	store {val}, {tv}
"""
		return TV()
	def visit_save(self, node:nodes.Save) -> TV:
		space = self.visit(node.space)
		value = self.visit(node.value)
		if value.typ == types.VOID:
			return TV()
		self.text += f"""\
	store {value}, {space}
"""
		return TV()
	def store_type_helper(self, space:TV, value:TV) -> None:
		if space.typ == types.VOID:
			return
		self.text += f"\tstore {value}, {space}\n"
	def visit_variable_save(self, node:nodes.VariableSave) -> TV:
		space = self.names.get(node.space.operand)
		value = self.visit(node.value)
		if space is None:
			space = self.allocate_type_helper(value.typ,node.uid)
			self.names[node.space.operand] = space
		self.store_type_helper(space,value)
		return TV()

	def visit_if(self, node:nodes.If) -> TV:
		cond = self.visit(node.condition)
		self.text+=f"""\
	br {cond}, label %ift{node.uid}, label %iff{node.uid}
ift{node.uid}:
"""
		self.visit(node.code)
		self.text+=f"""\
	br label %ife{node.uid}
iff{node.uid}:
"""
		if node.else_code is not None:
			self.visit(node.else_code)
		self.text+=f"""\
	br label %ife{node.uid}
ife{node.uid}:
"""
		return TV()
	def visit_while(self, node:nodes.While) -> TV:
		self.text+=f"""\
	br label %whilec{node.uid}
whilec{node.uid}:
"""
		cond = self.visit(node.condition)
		self.text+=f"""\
	br {cond}, label %whileb{node.uid}, label %whilee{node.uid}
whileb{node.uid}:
"""
		self.visit(node.code)
		self.text+=f"""\
	br label %whilec{node.uid}
whilee{node.uid}:
"""
		return TV()
	def visit_constant(self, node:nodes.Constant) -> TV:
		constants = {
			'False':TV(types.BOOL,'false'),
			'True' :TV(types.BOOL,'true'),
			'Null' :TV(types.Ptr(types.VOID) ,'null'),
			'Argv' :TV(types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))) ,f'%Argv{node.uid}'),
			'Argc' :TV(types.INT ,f'%Argc{node.uid}'),
			'Void' :TV(types.VOID),
		}
		if node.name.operand == 'Argv':
			self.text+=f"""\
	%Argv{node.uid} = load {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm}, {types.Ptr(types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR))))).llvm} @ARGV
"""
		if node.name.operand == 'Argc':
			self.text+=f"""\
	%Argc{node.uid} = load {types.INT.llvm}, {types.Ptr(types.INT).llvm} @ARGC
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
			assert isinstance(l,types.Ptr), f"{node} {op.loc} {val}"
			if l.pointed == types.VOID:
				return TV(types.VOID)
			i = f'load {node.typ(l).llvm}, {val}'
		else:
			assert False, f"Unreachable, {op = } and {l = }"
		self.text+=f"""\
	%uo{node.uid} = {i}
"""
		return TV(node.typ(l),f"%uo{node.uid}")
	def visit_const(self, node:nodes.Const) -> TV:
		return TV()
	def visit_struct(self, node:nodes.Struct) -> TV:
		for fun in node.funs:
			self.visit(fun)
		return TV()
	def visit_mix(self,node:nodes.Mix) -> TV:
		return TV()
	def visit_use(self,node:nodes.Use) -> TV:
		return TV()
	def visit_alias(self,node:nodes.Alias) -> TV:
		value = self.visit(node.value)
		self.names[node.name.operand] = value
		return TV()
	def visit_return(self, node:nodes.Return) -> TV:
		rv = self.visit(node.value)
		if rv.typ != types.VOID:
			self.text += f"""\
	store {rv}, {types.Ptr(rv.typ).llvm} %retvar
"""
		self.text+= "	br label %return\n"
		return TV()
	def visit_dot(self, node:nodes.Dot) -> TV:
		origin = self.visit(node.origin)
		if isinstance(origin.typ,types.Module):
			v = self.modules[origin.typ.module.uid].names.get(node.access.operand)
			assert v is not None
			return v
		if isinstance(origin.typ,types.StructKind):
			idx,typ = node.lookup_struct_kind(origin.typ)
			self.text += f"""\
    %tmp{node.uid} = getelementptr {origin.typ.llvm}, {TV(types.Ptr(origin.typ),origin.val)}, i32 0, i32 {idx}
	%dot{node.uid} = load {typ.llvm}, {types.Ptr(typ).llvm} %tmp{node.uid}
"""
			return TV(typ,f'%dot{node.uid}')
		assert isinstance(origin.typ,types.Ptr), f'dot lookup is not supported for {origin} yet'
		pointed = origin.typ.pointed
		if isinstance(pointed, types.Struct):
			struct = self.structs[pointed.name]
			r = node.lookup_struct(struct)
			if isinstance(r,tuple):
				idx,typ = r
				self.text += f"""\
	%dot{node.uid} = getelementptr {pointed.llvm}, {origin}, i32 0, i32 {idx}
"""
				return TV(types.Ptr(typ),f"%dot{node.uid}")
			return TV(types.BoundFun(r, origin.typ, origin.val), r.llvmid)
		else:
			assert False, f'unreachable, unknown {type(origin.typ.pointed) = }'
	def visit_get_item(self, node:nodes.GetItem) -> TV:
		origin = self.visit(node.origin)
		subscript = self.visit(node.subscript)
		assert subscript.typ == types.INT
		if origin.typ == types.STR:
			self.text += f"""\
	%tmp1{node.uid} = extractvalue {origin}, 1
	%tmp2{node.uid} = getelementptr {types.CHAR.llvm}, {types.Ptr(types.CHAR).llvm} %tmp1{node.uid}, {subscript}
	%gi{node.uid} = load i8, i8* %tmp2{node.uid}
"""
			return TV(types.CHAR,f"%gi{node.uid}")
		assert isinstance(origin.typ,types.Ptr), "unreachable"
		pointed = origin.typ.pointed
		if isinstance(pointed, types.Array):
			self.text +=f"""\
	%gi{node.uid} = getelementptr {pointed.llvm}, {origin}, i32 0, {subscript}
"""
			return TV(types.Ptr(pointed.typ),f'%gi{node.uid}')
		else:
			assert False, 'unreachable'
	def visit_string_cast(self, node:nodes.StrCast) -> TV:
		length = self.visit(node.length)
		pointer = self.visit(node.pointer)
		assert length.typ == types.INT
		assert pointer.typ == types.Ptr(types.CHAR)
		self.text += f"""\
	%tempore{node.uid} = insertvalue {types.STR.llvm} undef, {length}, 0
	%strcast{node.uid} = insertvalue {types.STR.llvm} %tempore{node.uid}, {pointer}, 1
"""
		return TV(types.STR,f"%strcast{node.uid}")
	def visit_cast(self, node:nodes.Cast) -> TV:
		val = self.visit(node.value)
		nt = node.typ
		vt = val.typ
		isptr:Callable[[types.Type],bool] = lambda t: isinstance(t,types.Ptr)

		if   (vt,nt)==(types.STR,types.INT):
			self.text += f"\t%extract{node.uid} = extractvalue {val}, 0\n"
			return TV(nt,f"%extract{node.uid}")
		elif (vt,nt)==(types.STR,types.Ptr(types.CHAR)):
			self.text += f"\t%extract{node.uid} = extractvalue {val}, 1\n"
			return TV(nt,f"%extract{node.uid}")
		elif isptr(vt) and isptr(nt)           :op = 'bitcast'
		elif (vt,nt)==(types.BOOL, types.CHAR ):op = 'zext'
		elif (vt,nt)==(types.BOOL, types.SHORT):op = 'zext'
		elif (vt,nt)==(types.BOOL, types.INT  ):op = 'zext'
		elif (vt,nt)==(types.CHAR, types.SHORT):op = 'zext'
		elif (vt,nt)==(types.CHAR, types.INT  ):op = 'zext'
		elif (vt,nt)==(types.SHORT,types.INT  ):op = 'zext'
		elif (vt,nt)==(types.INT,  types.SHORT):op = 'trunc'
		elif (vt,nt)==(types.INT,  types.CHAR ):op = 'trunc'
		elif (vt,nt)==(types.INT,  types.BOOL ):op = 'trunc'
		elif (vt,nt)==(types.SHORT,types.CHAR ):op = 'trunc'
		elif (vt,nt)==(types.SHORT,types.BOOL ):op = 'trunc'
		elif (vt,nt)==(types.CHAR, types.BOOL ):op = 'trunc'
		else:
			assert False, f"cast {vt} -> {nt} is not implemented yet"
		self.text += f"""\
	%cast{node.uid} = {op} {val} to {node.typ.llvm}
"""
		return TV(node.typ,f'%cast{node.uid}')
	def visit(self, node:Node|Token) -> TV:
		if type(node) == nodes.Import           : return self.visit_import          (node)
		if type(node) == nodes.FromImport       : return self.visit_from_import     (node)
		if type(node) == nodes.Fun              : return self.visit_fun             (node)
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
		if type(node) == nodes.Alias            : return self.visit_alias           (node)
		if type(node) == nodes.Return           : return self.visit_return          (node)
		if type(node) == nodes.Constant         : return self.visit_constant        (node)
		if type(node) == nodes.Dot              : return self.visit_dot             (node)
		if type(node) == nodes.GetItem          : return self.visit_get_item        (node)
		if type(node) == nodes.Cast             : return self.visit_cast            (node)
		if type(node) == nodes.StrCast          : return self.visit_string_cast     (node)
		if type(node) == Token                  : return self.visit_token           (node)
		assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		setup =''
		self.text = f"""
define private void @setup_{self.module.uid}() {{
"""
		for node in self.module.tops:
			if isinstance(node,nodes.Import):
				self.text+= f"\tcall void @setup_{node.module.uid}()\n"
				if node.module.path not in imported_modules_paths:
					gen = GenerateAssembly(node.module,self.config)
					setup+=gen.text
					imported_modules_paths[node.module.path] = gen
				else:
					gen = imported_modules_paths[node.module.path]
				self.modules[node.module.uid] = gen
				self.names[node.name] = TV(types.Module(node.module))
			elif isinstance(node,nodes.FromImport):
				self.text+= f"\tcall void @setup_{node.module.uid}()\n"
				if node.module.path not in imported_modules_paths:
					gen = GenerateAssembly(node.module,self.config)
					setup+=gen.text
					imported_modules_paths[node.module.path] = gen
				else:
					gen = imported_modules_paths[node.module.path]
				self.modules[node.module.uid] = gen
				for name in node.imported_names:
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
				self.names[node.name.operand] = TV(types.Fun([arg.typ for arg in node.arg_types], node.return_type),node.llvmid)
			elif isinstance(node,nodes.Const):
				self.names[node.name.operand] = TV(types.INT,f"{node.value}")
			elif isinstance(node,nodes.Struct):
				sk = types.StructKind(node)
				setup += f"""\
{types.Struct(node.name.operand, []).llvm} = type {{{', '.join(var.typ.llvm for var in node.variables)}}}
@__struct_static_{node.uid} = private global {sk.llvm} undef
"""
				self.structs[node.name.operand] = node
				self.names[node.name.operand] = TV(types.StructKind(node),f'@__struct_static_{node.uid}')
				u = node.uid
				for idx,i in enumerate(node.static_variables):
					value=self.visit(i.value)
					self.text+=f'''\
	%v{u}{idx+1} = insertvalue {sk.llvm} {f'%v{u}{idx}' if idx !=0 else 'undef'}, {value}, {idx}
'''
				l = len(node.static_variables)
				for idx,f in enumerate(node.funs):
					idx+=l
					value = TV(f.typ,f.llvmid)
					self.text+=f'''\
	%v{u}{idx+1} = insertvalue {sk.llvm} {f'%v{u}{idx}' if idx !=0 else 'undef'}, {value}, {idx}
'''
				l+=len(node.funs)
				if l != 0:
					self.text+=f'\tstore {sk.llvm} %v{u}{l}, {types.Ptr(sk).llvm} @__struct_static_{node.uid}'

			elif isinstance(node,nodes.Mix):
				self.names[node.name.operand] = TV(MixTypeTv([self.visit(fun_ref) for fun_ref in node.funs],node.name.operand))
			elif isinstance(node,nodes.Use):
				self.names[node.name.operand] = TV(types.Fun(node.arg_types,node.return_type),f'@{node.name}')
				setup+=f"declare {node.return_type.llvm} @{node.name}({', '.join(arg.llvm for arg in node.arg_types)})\n"
		self.text+="\tret void\n}"
		text = ''
		if self.module.path == '__main__':
			text += f"""\
; Assembly generated by jararaca compiler github.com/izumrudik/jararaca
@ARGV = private global {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm} undef
@ARGC = private global {types.INT.llvm} undef
declare void @GC_init()
declare i8* @GC_malloc(i64)
"""
		text+=f"""\
; --------------------------- start of module {self.module.path}
"""
		for node in self.module.tops:
			self.visit(node)
		for string in self.strings:
			l = len(string.operand)
			st = ''.join('\\'+('0'+hex(ord(c))[2:])[-2:] for c in string.operand)
			text += f"@.str.{string.uid} = private constant [{l} x i8] c\"{st}\"\n"
		self.text = text+setup+self.text
		if self.config.verbose:
			self.text+=f"""
; --------------------------- end of module {self.module.path}
; DEBUG:
; there was {len(self.module.tops)} tops in this module
; state of id counter: {id_counter}
"""
