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
	__slots__ = ('text','module','config', 'funs', 'strings', 'names', 'modules')
	def __init__(self, module:nodes.Module, config:Config) -> None:
		self.config   :Config                    = config
		self.module   :nodes.Module              = module
		self.text     :str                       = ''
		self.strings  :list[Token]               = []
		self.names    :dict[str,TV]              = {}
		self.modules  :dict[int,GenerateAssembly]= {}
		self.generate_assembly()
	def visit_from_import(self,node:nodes.FromImport) -> TV:
		return TV()
	def visit_import(self, node:nodes.Import) -> TV:
		return TV()
	def visit_fun(self, node:nodes.Fun) -> TV:
		for arg in node.arg_types:
			self.names[arg.name.operand] = TV(arg.typ,f'%argument{arg.uid}')
		ot = node.return_type
		if node.name.operand == 'main':
			self.text += f"""
define i64 @main(i32 %0, i8** %1){{;entry point
	call void @GC_init()
	%3 = zext i32 %0 to {types.INT.llvm}
	%4 = bitcast i8** %1 to {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm}
	store {types.INT.llvm} %3, {types.Ptr(types.INT).llvm} @ARGC, align 1
	store {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm} %4, {types.Ptr(types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR))))).llvm} @ARGV, align 1
"""
		else:
			self.text += f"""
define private {ot.llvm} @{node.name}\
({', '.join(f'{arg.typ.llvm} %argument{arg.uid}' for arg in node.arg_types)}) {{
{f'	%retvar = alloca {ot.llvm}{NEWLINE}' if ot != types.VOID else ''}\
"""
		self.visit(node.code)

		if node.name.operand == 'main':
			self.text += f"""\
	call void @GC_gcollect()
	ret i64 0
}}
"""
			assert node.arg_types == []
			assert node.return_type == types.VOID
			return TV()
		self.text += f"""\
	{f'br label %return' if ot == types.VOID else 'unreachable'}
	return:
{f'	%retval = load {ot.llvm}, {ot.llvm}* %retvar{NEWLINE}' if ot != types.VOID else ''}\
	ret {ot.llvm} {f'%retval' if ot != types.VOID else ''}
}}
"""
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
				assert False, f"ERROR: {node.loc} did not find function to match {tuple(actual_types)!s} in mix '{called}'"
			assert False, f"ERROR: {node.loc}: '{called}' object is not callable"

		fun = get_fun_out_of_called(self.visit(node.func))
		assert isinstance(fun.typ,types.Fun), f'python typechecker is not robust enough'
		self.text+='\t'
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
			TT.PERCENT_SIGN:             f"srem {left}, {rv}",
			TT.PLUS:                  f"add nsw {left}, {rv}",
			TT.MINUS:                 f"sub nsw {left}, {rv}",
			TT.ASTERISK:              f"mul nsw {left}, {rv}",
			TT.DOUBLE_SLASH:             f"sdiv {left}, {rv}",
			TT.LESS_SIGN:            f"icmp slt {left}, {rv}",
			TT.LESS_OR_EQUAL_SIGN:   f"icmp sle {left}, {rv}",
			TT.GREATER_SIGN:         f"icmp sgt {left}, {rv}",
			TT.GREATER_OR_EQUAL_SIGN:f"icmp sge {left}, {rv}",
			TT.DOUBLE_EQUALS_SIGN:    f"icmp eq {left}, {rv}",
			TT.NOT_EQUALS_SIGN:       f"icmp ne {left}, {rv}",
			TT.DOUBLE_LESS_SIGN:          f"shl {left}, {rv}",
			TT.DOUBLE_GREATER_SIGN:      f"ashr {left}, {rv}",
			}.get(node.operation.typ)
			if op.equals(TT.KEYWORD,'xor'):implementation = f'xor {left}, {rv}'
			if op.equals(TT.KEYWORD, 'or'):implementation =  f'or {left}, {rv}'
			if op.equals(TT.KEYWORD,'and'):implementation = f'and {left}, {rv}'
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
		assert tv is not None, f"{node.name.loc} name '{node.name.operand}' is not defined (tc is broken)"
		return tv
	def visit_new_declaration(self, node:nodes.NewDeclaration) -> TV:
		self.names[node.var.name.operand] = TV(types.Ptr(node.var.typ), f"%nv{node.uid}")
		self.text += f"""\
	%tmp{node.uid} = call i8* @GC_malloc(i64 ptrtoint({types.Ptr(node.var.typ).llvm} getelementptr({node.var.typ.llvm}, {types.Ptr(node.var.typ).llvm} null, i64 1) to i64))
	%nv{node.uid} = bitcast i8* %tmp{node.uid} to {types.Ptr(node.var.typ).llvm}
"""
		return TV()
	def visit_assignment(self, node:nodes.NewAssignment) -> TV:
		val = self.visit(node.value) # get a value to store
		self.names[node.var.name.operand] = TV(types.Ptr(val.typ),f'%nv{node.uid}')
		self.text += f"""\
	%tmp{node.uid} = call i8* @GC_malloc(i64 ptrtoint({types.Ptr(node.var.typ).llvm} getelementptr({node.var.typ.llvm}, {types.Ptr(node.var.typ).llvm} null, i64 1) to i64))
        %nv{node.uid} = bitcast i8* %tmp{node.uid} to {types.Ptr(node.var.typ).llvm}
	store {val}, {types.Ptr(val.typ).llvm} %nv{node.uid},align 4
"""
		return TV()
	def visit_save(self, node:nodes.Save) -> TV:
		space = self.visit(node.space)
		value = self.visit(node.value)
		self.text += f"""\
	store {value}, {space},align 4
"""
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
			'Null' :TV(types.Ptr(types.BOOL) ,'null'),
			'Argv' :TV(types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))) ,f'%Argv{node.uid}'),
			'Argc' :TV(types.INT ,f'%Argc{node.uid}'),
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
		elif op == TT.AT_SIGN: i = f'load {node.typ(l).llvm}, {val}'
		else:
			assert False, f"Unreachable, {op = } and {l = }"
		self.text+=f"""\
	%uo{node.uid} = {i}
"""

		return TV(node.typ(l),f"%uo{node.uid}")
	def visit_var(self, node:nodes.Var) -> TV:
		return TV()
	def visit_const(self, node:nodes.Const) -> TV:
		return TV()
	def visit_struct(self, node:nodes.Struct) -> TV:
		return TV()
	def visit_mix(self,node:nodes.Mix) -> TV:
		return TV()
	def visit_use(self,node:nodes.Use) -> TV:
		return TV()
	def visit_return(self, node:nodes.Return) -> TV:
		rv = self.visit(node.value)
		self.text += f"""\
	store {rv}, {types.Ptr(rv.typ).llvm} %retvar
	br label %return
"""
		return TV()
	def visit_dot(self, node:nodes.Dot) -> TV:
		origin = self.visit(node.origin)
		if isinstance(origin.typ,types.Module):
			v = self.modules[origin.typ.module.uid].names.get(node.access.operand)
			assert v is not None
			return v
		assert isinstance(origin.typ,types.Ptr), f'dot lookup is not supported for {origin} yet'
		pointed = origin.typ.pointed
		if isinstance(pointed, types.Struct):
			idx,typ = node.lookup_struct(pointed.struct)
			self.text += f"""\
	%dot{node.uid} = getelementptr {pointed.llvm}, {origin}, i32 0, i32 {idx}
"""
			return TV(types.Ptr(typ),f"%dot{node.uid}")
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
		if type(node) == nodes.NewAssignment       : return self.visit_assignment      (node)
		if type(node) == nodes.ReferTo          : return self.visit_refer           (node)
		if type(node) == nodes.NewDeclaration      : return self.visit_new_declaration     (node)
		if type(node) == nodes.Save             : return self.visit_save            (node)
		if type(node) == nodes.If               : return self.visit_if              (node)
		if type(node) == nodes.While            : return self.visit_while           (node)
		if type(node) == nodes.Return           : return self.visit_return          (node)
		if type(node) == nodes.Constant         : return self.visit_constant        (node)
		if type(node) == nodes.Dot              : return self.visit_dot             (node)
		if type(node) == nodes.GetItem          : return self.visit_get_item        (node)
		if type(node) == nodes.Cast             : return self.visit_cast            (node)
		if type(node) == nodes.StrCast          : return self.visit_string_cast     (node)
		if type(node) == Token                  : return self.visit_token           (node)
		assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:

		for node in self.module.tops:
			if isinstance(node,nodes.Import):
				if node.module.path not in imported_modules_paths:
					gen = GenerateAssembly(node.module,self.config)
					self.text+=gen.text
					imported_modules_paths[node.module.path] = gen
				else:
					gen = imported_modules_paths[node.module.path]
				self.modules[node.module.uid] = gen
				self.names[node.name] = TV(types.Module(node.module))
			elif isinstance(node,nodes.FromImport):
				if node.module.path not in imported_modules_paths:
					gen = GenerateAssembly(node.module,self.config)
					self.text+=gen.text
					imported_modules_paths[node.module.path] = gen
				else:
					gen = imported_modules_paths[node.module.path]
				self.modules[node.module.uid] = gen
				for name in node.imported_names:
					typ = gen.names.get(name.operand)
					if typ is not None:
						self.names[name.operand] = gen.names[name.operand]
						continue
			elif isinstance(node,nodes.Fun):
				self.names[node.name.operand] = TV(types.Fun([arg.typ for arg in node.arg_types], node.return_type),f'@{node.name}')
			elif isinstance(node,nodes.Var):
				self.names[node.name.operand] = TV(types.Ptr(node.typ),f"@{node.name}")
				self.text += f"@{node.name} = private global {node.typ.llvm} undef\n"
			elif isinstance(node,nodes.Const):
				self.names[node.name.operand] = TV(types.INT,f"{node.value}")
			elif isinstance(node,nodes.Struct):
				self.text += f"{types.Struct(node).llvm} = type {{{', '.join(var.typ.llvm for var in node.variables)}}}\n"
			elif isinstance(node,nodes.Mix):
				self.names[node.name.operand] = TV(MixTypeTv([self.visit(fun_ref) for fun_ref in node.funs],node.name.operand))
			elif isinstance(node,nodes.Use):
				self.names[node.name.operand] = TV(types.Fun(node.arg_types,node.return_type),f'@{node.name}')
				self.text+=f"declare {node.return_type.llvm} @{node.name}({', '.join(arg.llvm for arg in node.arg_types)})\n"
		text = ''
		if self.module.path == '__main__':
			text += f"""\
; Assembly generated by jararaca compiler github.com/izumrudik/jararaca
@ARGV = private global {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm} zeroinitializer, align 1
@ARGC = private global {types.INT.llvm} zeroinitializer, align 1
declare void @GC_init()
declare i8* @GC_malloc(i64)
declare void @GC_gcollect()
"""
		text+=f"""\
; --------------------------- start of module {self.module.path}
"""
		for node in self.module.tops:
			self.visit(node)
		for string in self.strings:
			l = len(string.operand)
			st = ''.join('\\'+('0'+hex(ord(c))[2:])[-2:] for c in string.operand)
			text += f"@.str.{string.uid} = private constant [{l} x i8] c\"{st}\", align 1"
		self.text = text+self.text
		if self.config.verbose:
			self.text+=f"""
; --------------------------- end of module {self.module.path}
; DEBUG:
; there was {len(self.module.tops)} tops in this module
; state of id counter: {id_counter}
"""
