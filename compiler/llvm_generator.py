from typing import Callable
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, find_fun_by_name, id_counter, Type, types
from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class TV:#typed value
	typ:'Type|None'  = None
	val:'str' = ''
	def __str__(self) -> str:
		if self.typ is None:
			return f"<None TV>"
		return f"{self.typ.llvm} {self.val}"
class GenerateAssembly:
	__slots__ = ('text','ast','config', 'variables', 'structs', 'consts', 'funs', 'vars', 'strings', 'intrnsics')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.config   :Config                    = config
		self.ast      :nodes.Tops                = ast
		self.text     :str                       = ''
		self.vars     :list[nodes.Var]           = []
		self.consts   :list[nodes.Const]         = []
		self.structs  :list[nodes.Struct]        = []
		self.strings  :list[Token]               = []
		self.variables:list[nodes.TypedVariable] = []
		self.intrnsics:set[int]                  = set()
		self.generate_assembly()
	def visit_fun(self, node:nodes.Fun) -> TV:
		assert self.variables == [], f"visit_fun called with {[str(var) for var in self.variables]} (vars should be on the stack) at {node}"
		self.variables = node.arg_types.copy()
		ot = node.return_type
		if node.name.operand == 'main':
			self.text += f"""
@ARGV = global {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm} zeroinitializer, align 1
@ARGC = global {types.INT.llvm} zeroinitializer, align 1
define i64 @main(i32 %0, i8** %1){{;entry point
	%3 = zext i32 %0 to {types.INT.llvm}
	%4 = bitcast i8** %1 to {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm}
	store {types.INT.llvm} %3, {types.Ptr(types.INT).llvm} @ARGC, align 1
	store {types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR)))).llvm} %4, {types.Ptr(types.Ptr(types.Array(0,types.Ptr(types.Array(0,types.CHAR))))).llvm} @ARGV, align 1
"""
		else:
			self.text += f"""
define {ot.llvm} @{node.name}\
({', '.join(f'{arg.typ.llvm} %argument{arg.uid}' for arg in node.arg_types)}) {{
{f'	%retvar = alloca {ot.llvm}{NEWLINE}' if ot != types.VOID else ''}\
{''.join(f'''	%v{arg.uid} = alloca {arg.typ.llvm}
	store {arg.typ.llvm} %argument{arg.uid}, {types.Ptr(arg.typ).llvm} %v{arg.uid},align 4
''' for arg in node.arg_types)}"""
		
		self.visit(node.code)

		self.variables = []
		if node.name.operand == 'main':
			self.text += f"	ret i64 0\n}}\n"
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
		var_before = self.variables.copy()
		for statemnet in node.statements:
			self.visit(statemnet)
		self.variables = var_before
		return TV()
	def visit_function_call(self, node:nodes.FunctionCall) -> TV:
		args = [self.visit(arg) for arg in node.args]
		rt:Type
		_,rt,name = find_fun_by_name(self.ast, node.name,[arg.typ for arg in args])
		self.text+='\t'
		if rt != types.VOID:
			self.text+=f"""\
%callresult{node.uid} = """

		self.text += f"""\
call {rt.llvm} {name}({', '.join(str(a) for a in args)})
"""
		if rt != types.VOID:
			return TV(rt, f"%callresult{node.uid}")
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
		implementation:'None|str' = None
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
		assert implementation is not None, f"op '{node.operation}' is not implemented yet for {left.typ}, {right.typ}"
		self.text+=f"""\
	%bin_op{node.uid} = {implementation}
"""


		return TV(node.typ(left.typ, right.typ), f"%bin_op{node.uid}")
	def visit_expr_state(self, node:nodes.ExprStatement) -> TV:
		self.visit(node.value)
		return TV()
	def visit_refer(self, node:nodes.ReferTo) -> TV:
		def refer_to_var(var:nodes.Var) -> TV:
			return TV(types.Ptr(var.typ),
				f"@{var.name}"
			)
		def refer_to_const(const:nodes.Const) -> TV:
			return TV(types.INT,f"{const.value}")

		def refer_to_variable() -> TV:
			for variable in self.variables:
				if node.name == variable.name:
					typ = variable.typ
					self.text+=f"""\
	%refer{node.uid} = load {typ.llvm}, {types.Ptr(typ).llvm} %v{variable.uid}
"""
					return TV(typ,f'%refer{node.uid}')
			assert False, "type checker is broken"
		for var in self.vars:
			if node.name == var.name:
				return refer_to_var(var)
		for const in self.consts:
			if node.name == const.name:
				return refer_to_const(const)
		return refer_to_variable()
	def visit_defining(self, node:nodes.Defining) -> TV:
		self.variables.append(node.var)
		self.text += f"""\
	%v{node.var.uid} = alloca {node.var.typ.llvm}
"""
		return TV()
	def visit_reassignment(self, node:nodes.ReAssignment) -> TV:
		val = self.visit(node.value)
		for variable in self.variables:
			if node.name == variable.name:
				var = variable
				break
		else:#auto
			var = nodes.TypedVariable(node.name,val.typ,uid=node.uid)#sneaky, but works
			self.variables.append(var)
			self.text += f"""\
	%v{node.uid} = alloca {val.typ.llvm}
"""	
		self.text += f"""\
	store {val}, {types.Ptr(val.typ).llvm} %v{var.uid},align 4
"""
		return TV()
	def visit_assignment(self, node:nodes.Assignment) -> TV:
		val = self.visit(node.value) # get a value to store
		self.variables.append(node.var)
		self.text += f"""\
	%v{node.var.uid} = alloca {node.var.typ.llvm}
	store {val}, {types.Ptr(val.typ).llvm} %v{node.var.uid},align 4
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
	def visit_intr_constant(self, node:nodes.Constant) -> TV:
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
		self.vars.append(node)
		return TV()
	def visit_const(self, node:nodes.Const) -> TV:
		self.consts.append(node)
		return TV()
	def visit_struct(self, node:nodes.Struct) -> TV:
		self.structs.append(node)
		return TV()
	def visit_mix(self,node:nodes.Mix) -> TV:
		return TV()
	def visit_use(self,node:nodes.Use) -> TV:
		self.text+=f"""\
declare {node.return_type.llvm} @{node.name}({', '.join(arg.llvm for arg in node.arg_types)})
"""
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
	def visit_dot_call(self, node:nodes.DotCall) -> TV:
		origin = self.visit(node.origin)
		assert isinstance(origin.typ,types.Ptr), f'dot lookup is not supported for {origin} yet'
		pointed = origin.typ.pointed
		args:list[TV] = []
		if isinstance(pointed, types.Struct):
			fun = node.lookup_struct(pointed.struct,self.ast)
			args = [origin]
		else:
			assert False, f'unreachable, unknown {type(origin.typ.pointed) = }'
		args += [self.visit(arg) for arg in node.access.args]
		if fun.return_type != types.VOID:
			self.text += f"""\
	%dotcall{node.uid} = call {fun.return_type.llvm} @{fun.name}({', '.join(f'{arg}' for arg in args)})
"""
			return TV(fun.return_type, f"%dotcall{node.uid}")
		else:
			self.text += f"""\
	call void @{fun.name}({', '.join(f'{arg}' for arg in args)})
"""
			return TV(types.VOID)
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
			self.text += f"%extract{node.uid} = extractvalue {val}, 0\n"
			return TV(nt,f"%extract{node.uid}")
		elif (vt,nt)==(types.STR,types.Ptr(types.CHAR)):
			self.text += f"%extract{node.uid} = extractvalue {val}, 1\n"
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
	def visit(self, node:'Node|Token') -> TV:
		if type(node) == nodes.Fun              : return self.visit_fun          (node)
		if type(node) == nodes.Var              : return self.visit_var          (node)
		if type(node) == nodes.Const            : return self.visit_const        (node)
		if type(node) == nodes.Struct           : return self.visit_struct       (node)
		if type(node) == nodes.Code             : return self.visit_code         (node)
		if type(node) == nodes.Mix              : return self.visit_mix          (node)
		if type(node) == nodes.Use              : return self.visit_use          (node)
		if type(node) == nodes.FunctionCall     : return self.visit_function_call(node)
		if type(node) == nodes.BinaryExpression : return self.visit_bin_exp      (node)
		if type(node) == nodes.UnaryExpression  : return self.visit_unary_exp    (node)
		if type(node) == nodes.ExprStatement    : return self.visit_expr_state   (node)
		if type(node) == nodes.Assignment       : return self.visit_assignment   (node)
		if type(node) == nodes.ReferTo          : return self.visit_refer        (node)
		if type(node) == nodes.Defining         : return self.visit_defining     (node)
		if type(node) == nodes.ReAssignment     : return self.visit_reassignment (node)
		if type(node) == nodes.Save             : return self.visit_save         (node)
		if type(node) == nodes.If               : return self.visit_if           (node)
		if type(node) == nodes.While            : return self.visit_while        (node)
		if type(node) == nodes.Return           : return self.visit_return       (node)
		if type(node) == nodes.Constant: return self.visit_intr_constant(node)
		if type(node) == nodes.Dot              : return self.visit_dot          (node)
		if type(node) == nodes.DotCall          : return self.visit_dot_call     (node)
		if type(node) == nodes.GetItem          : return self.visit_get_item     (node)
		if type(node) == nodes.Cast             : return self.visit_cast         (node)
		if type(node) == nodes.StrCast          : return self.visit_string_cast  (node)
		if type(node) == Token                  : return self.visit_token        (node)
		assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		text="""\
; Assembly generated by lang compiler github.com/izumrudik/compile
; ---------------------------
"""
		for top in self.ast.tops:
			self.visit(top)
		for struct in self.structs:
			text += f"{types.Struct(struct).llvm} = type {{{', '.join(var.typ.llvm for var in struct.variables)}}}\n"
		for var in self.vars:
			text += f"@{var.name} = global {var.typ.llvm} zeroinitializer, align 1\n"
		for string in self.strings:
			l = len(string.operand)
			st = ''.join('\\'+('0'+hex(ord(c))[2:])[-2:] for c in string.operand)
			text += f"@.str.{string.uid} = constant [{l} x i8] c\"{st}\", align 1"
		self.text = text+self.text
		if self.config.verbose:
			self.text+=f"""
; ---------------------------
; DEBUG:
; there was {len(self.ast.tops)} tops
; constant values:
{''.join(f';	{const.name} = {const.value}{NEWLINE}' for const in self.consts)
}; state of id counter: {id_counter}
"""
		if self.config.interpret:
			return
		with open(self.config.output_file + '.ll', 'wt', encoding='UTF-8') as file:
			file.write(self.text)
