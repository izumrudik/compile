from sys import implementation, stderr
import sys
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, id_counter, safe, INTRINSICS_TYPES, Type, Ptr, INT, BOOL, STR, VOID, PTR, find_fun_by_name, StructType
from dataclasses import dataclass
__INTRINSICS_IMPLEMENTATION:'dict[str,str]' = {
	'exit':f"""declare void @exit(i32)
define void @exit_({INT.llvm} %0) {{
	%2 = trunc i64 %0 to i32
	call void @exit(i32 %2)
	unreachable
}}\n""",
	'puts':f"""declare i64 @write(i64,i8*,i64)
define i64 @puts_({STR.llvm} %0) {{
	%2 = extractvalue {STR.llvm} %0, 0
	%3 = extractvalue {STR.llvm} %0, 1
	%4 = call i64 @write(i64 1,i8* %3,i64 %2)
	ret i64 %4
}}\n""",
}
INTRINSICS_IMPLEMENTATION:'dict[int,tuple[str,str]]' = {
	INTRINSICS_TYPES[name][2]:(name,__INTRINSICS_IMPLEMENTATION[name]) for name in __INTRINSICS_IMPLEMENTATION
}
@dataclass
class TV:#typed value
	typ:'Type|None'  = None
	val:'str' = ''
	def __str__(self) -> str:
		if self.typ is None:
			return f"<None TV>"
		return f"{self.typ.llvm} {self.val}"
class GenerateAssembly:
	__slots__ = ('text','ast','config', 'variables', 'funs', 'strings')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.config   :Config                    = config
		self.ast      :nodes.Tops                = ast
		self.text     :str                       = ''
		self.variables:list[nodes.TypedVariable] = []
		self.funs     :list[nodes.Fun]           = []
		self.strings  :list[Token]               = []
		self.generate_assembly()
	def visit_fun(self, node:nodes.Fun) -> TV:
		self.funs.append(node)
		assert self.variables == [], f"visit_fun called with {[str(var) for var in self.variables]} (vars should be on the stack) at {node}"
		self.variables = node.arg_types.copy()
		ot = node.output_type
		self.text += f"""
define {ot.llvm} @fun_{node.identifier}\
({', '.join(f'{arg.typ.llvm} %argument{arg.identifier}' for arg in node.arg_types)}) {{
{f'	%retvar = alloca {ot.llvm}, align 4{NEWLINE}' if ot != VOID else ''}\
{''.join(f'''	%v{arg.identifier} = alloca {arg.typ.llvm}, align 4
	store {arg.typ.llvm} %argument{arg.identifier}, {Ptr(arg.typ).llvm} %v{arg.identifier},align 4
''' for arg in node.arg_types)}"""
		self.visit(node.code)


		self.text += f"""\
	{f'br label %return' if ot == VOID else 'unreachable'}		
return:
{f'	%retval = load {ot.llvm}, {ot.llvm}* %retvar, align 4{NEWLINE}' if ot != VOID else ''}\
	ret {ot.llvm} {f'%retval' if ot != VOID else ''}
}}
"""
		self.variables = []
		return TV()
	def visit_code(self, node:nodes.Code) -> TV:
		var_before = self.variables.copy()
		for statemnet in node.statements:
			self.visit(statemnet)
		self.variables = var_before
		return TV()
	def visit_function_call(self, node:nodes.FunctionCall) -> TV:
		args = [self.visit(arg) for arg in node.args]
		intrinsic = INTRINSICS_TYPES.get(node.name.operand)
		rt:Type
		if intrinsic is not None:
			rt = intrinsic[1]
			name = f"@{node.name.operand}_"
		else:
			for fun in self.funs:
				if fun.name == node.name:
					rt = fun.output_type
					name = f"@fun_{fun.identifier}"
					break
			else:
				assert False, "type checker is broken"
		if rt != VOID:
			self.text+=f"""\
	%callresult{node.identifier} = """
		self.text += f"""\
call {rt.llvm} {name}({', '.join(str(a) for a in args)})
"""
		if rt != VOID:
			return TV(rt, f"%callresult{node.identifier}")
		return TV(VOID)
	def visit_token(self, token:Token) -> TV:
		if token.typ == TT.DIGIT:
			return TV(INT, token.operand)
		elif token.typ == TT.STRING:
			self.strings.append(token)
			l = len(token.operand)
			u = token.identifier
			return TV(STR,f"<{{i64 {l}, i8* bitcast([{l} x i8]* @.str.{u} to i8*)}}>")
		else:
			assert False, f"Unreachable: {token.typ=}"
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> TV:
		left = self.visit(node.left)
		right = self.visit(node.right)
		lr = left.typ,right.typ
		lv = left.val
		rv = right.val
		operations = {
			TT.PERCENT_SIGN:             f"srem {INT.llvm} {lv}, {rv}",
			TT.MINUS:                 f"sub nsw {INT.llvm} {lv}, {rv}",
			TT.ASTERISK:              f"mul nsw {INT.llvm} {lv}, {rv}",
			TT.DOUBLE_SLASH:             f"sdiv {INT.llvm} {lv}, {rv}",
			TT.LESS_SIGN:            f"icmp slt {INT.llvm} {lv}, {rv}",
			TT.LESS_OR_EQUAL_SIGN:   f"icmp sle {INT.llvm} {lv}, {rv}",
			TT.GREATER_SIGN:         f"icmp sgt {INT.llvm} {lv}, {rv}",
			TT.GREATER_OR_EQUAL_SIGN:f"icmp sge {INT.llvm} {lv}, {rv}",
			TT.DOUBLE_EQUALS_SIGN:    f"icmp eq {INT.llvm} {lv}, {rv}",
			TT.NOT_EQUALS_SIGN:       f"icmp ne {INT.llvm} {lv}, {rv}",
			TT.DOUBLE_LESS_SIGN:          f"shl {INT.llvm} {lv}, {rv}",
			TT.DOUBLE_GREATER_SIGN:      f"ashr {INT.llvm} {lv}, {rv}",
}
		op = node.operation
		implementation:'None|str' = None
		if   op == TT.PLUS:
			if lr == (INT,INT):implementation = f'add nsw {INT.llvm} {lv}, {rv}'
		elif op.equals(TT.KEYWORD,'and'):
			if lr == (INT ,INT ):implementation = f'and {INT .llvm} {lv}, {rv}'
			if lr == (BOOL,BOOL):implementation = f'and {BOOL.llvm} {lv}, {rv}'
		elif op.equals(TT.KEYWORD,'or' ):
			if lr == (INT ,INT ):implementation = f'or { INT .llvm} {lv}, {rv}'
			if lr == (BOOL,BOOL):implementation = f'or { BOOL.llvm} {lv}, {rv}'
		elif op.equals(TT.KEYWORD,'xor'):
			if lr == (INT ,INT ):implementation = f'xor {INT .llvm} {lv}, {rv}'
			if lr == (BOOL,BOOL):implementation = f'xor {BOOL.llvm} {lv}, {rv}'
		else:
			implementation = operations.get(node.operation.typ)
		assert implementation is not None, f"op '{node.operation}' is not implemented yet"
		self.text+=f"""\
	%bin_op{node.identifier} = {implementation}
"""


		return TV(node.typ(left.typ, right.typ), f"%bin_op{node.identifier}")
	def visit_expr_state(self, node:nodes.ExprStatement) -> TV:
		self.visit(node.value)
		return TV()
	def visit_refer(self, node:nodes.ReferTo) -> TV:
		'''
		def refer_to_var(var:nodes.Var) -> None:
			self.file.write(f"""
	push var_{var.identifier}{self.debug(f"; push {Ptr(var.typ)} to var at {node.name.loc}{NEWLINE}")}""")
			self.data_stack.append(Ptr(var.typ))
			return
		def refer_to_memo(memo:nodes.Memo) -> None:
			self.file.write(f"""
	push memo_{memo.identifier}{self.debug(f"; push PTR to memo at {node.name.loc}{NEWLINE}")}""")
			self.data_stack.append(PTR)
			return
		def refer_to_const(const:nodes.Const) -> None:
			self.file.write(f"""
	push {const.value}{self.debug(f"; push const value of {const.name} at {node.name.loc}{NEWLINE}")}""")
			self.data_stack.append(INT)
			return
		'''
		def refer_to_variable() -> TV:
			for variable in self.variables:
				if node.name == variable.name:
					typ = variable.typ
					self.text+=f"""\
	%refer{node.identifier} = load {typ.llvm}, {Ptr(typ).llvm} %v{variable.identifier}, align 4
"""
					return TV(typ,f'%refer{node.identifier}')
			assert False, "type checker is broken"
		#for var in self.vars:
		#	if node.name == var.name:
		#		return refer_to_var(var)
		#for memo in self.memos:
		#	if node.name == memo.name:
		#		return refer_to_memo(memo)
		#for const in self.consts:
		#	if node.name == const.name:
		#		return refer_to_const(const)
		return refer_to_variable()
	def visit_defining(self, node:nodes.Defining) -> TV:
		self.variables.append(node.var)
		self.text += f"""\
	%v{node.var.identifier} = alloca {node.var.typ.llvm}, align 4
"""
		return TV()
	def visit_reassignment(self, node:nodes.ReAssignment) -> TV:
		val = self.visit(node.value)
		for variable in self.variables:
			if node.name == variable.name:
				break
		else:
			assert False, "type checker does not work"
		self.text += f"""\
	store {val}, {Ptr(val.typ).llvm} %v{variable.identifier},align 4 
"""
		return TV()
	def visit_assignment(self, node:nodes.Assignment) -> TV:
		val = self.visit(node.value) # get a value to store
		self.variables.append(node.var)
		self.text += f"""\
	%v{node.var.identifier} = alloca {node.var.typ.llvm}, align 4
	store {val}, {Ptr(val.typ).llvm} %v{node.var.identifier},align 4 
"""
		return TV()
	def visit_if(self, node:nodes.If) -> TV:
		assert False, 'visit_if is not implemented yet'
	def visit_while(self, node:nodes.While) -> TV:
		assert False, 'visit_while is not implemented yet'
	def visit_intr_constant(self, node:nodes.IntrinsicConstant) -> TV:
		constants = {
			'False':TV(BOOL,'0'),
			'True' :TV(BOOL,'1'),
		}
		implementation = constants.get(node.name.operand)
		assert implementation is not None, f"Constant {node.name} is not implemented yet"
		return implementation
	def visit_unary_exp(self, node:nodes.UnaryExpression) -> TV:
		assert False, 'visit_unary_exp is not implemented yet'
	def visit_var(self, node:nodes.Var) -> TV:
		assert False, 'visit_var is not implemented yet'
	def visit_memo(self, node:nodes.Memo) -> TV:
		assert False, 'visit_memo is not implemented yet'
	def visit_const(self, node:nodes.Const) -> TV:
		assert False, 'visit_const is not implemented yet'
	def visit_struct(self, node:nodes.Struct) -> TV:
		assert False, 'visit_struct is not implemented yet'
	def visit_return(self, node:nodes.Return) -> TV:
		rv = self.visit(node.value)
		self.text += f"""\
	store {rv}, {Ptr(rv.typ).llvm} %retvar, align 4
	br label %return
"""
		return TV()
	def visit_dot(self, node:nodes.Dot) -> TV:
		assert False, 'visit_dot is not implemented yet'
	def visit_cast(self, node:nodes.Cast) -> TV:
		val = self.visit(node.value)
		nt = node.typ
		vt = val.typ
		op = None
		if isinstance(vt,Ptr) and isinstance(nt,Ptr):op = 'bitcast'
		if (vt,nt) ==(BOOL,INT):op = 'zext'
		if (vt,nt) ==(INT,BOOL):op = 'trunc'
		assert op is not None, f"cast {vt} -> {nt} is not implemented yet"
		self.text += f"""\
	%cast{node.identifier} = {op} {val} to {node.typ.llvm}
"""
		return TV(node.typ,f'%cast{node.identifier}')
	def visit(self, node:'Node|Token') -> TV:
		if   type(node) == nodes.Fun              : return self.visit_fun          (node)
		elif type(node) == nodes.Var              : return self.visit_var          (node)
		elif type(node) == nodes.Memo             : return self.visit_memo         (node)
		elif type(node) == nodes.Const            : return self.visit_const        (node)
		elif type(node) == nodes.Struct           : return self.visit_struct       (node)
		elif type(node) == nodes.Code             : return self.visit_code         (node)
		elif type(node) == nodes.FunctionCall     : return self.visit_function_call(node)
		elif type(node) == nodes.BinaryExpression : return self.visit_bin_exp      (node)
		elif type(node) == nodes.UnaryExpression  : return self.visit_unary_exp    (node)
		elif type(node) == nodes.ExprStatement    : return self.visit_expr_state   (node)
		elif type(node) == nodes.Assignment       : return self.visit_assignment   (node)
		elif type(node) == nodes.ReferTo          : return self.visit_refer        (node)
		elif type(node) == nodes.Defining         : return self.visit_defining     (node)
		elif type(node) == nodes.ReAssignment     : return self.visit_reassignment (node)
		elif type(node) == nodes.If               : return self.visit_if           (node)
		elif type(node) == nodes.While            : return self.visit_while        (node)
		elif type(node) == nodes.Return           : return self.visit_return       (node)
		elif type(node) == nodes.IntrinsicConstant: return self.visit_intr_constant(node)
		elif type(node) == nodes.Dot              : return self.visit_dot          (node)
		elif type(node) == nodes.Cast             : return self.visit_cast         (node)
		elif type(node) == Token                  : return self.visit_token        (node)
		else:
			assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		self.text+="""\
; Assembly generated by lang compiler github.com/izumrudik/compile
; ---------------------------
"""
		for top in self.ast.tops:
			self.visit(top)
		for (name,implementation) in INTRINSICS_IMPLEMENTATION.values():
			self.text += implementation
		for string in self.strings:
			l = len(string.operand)
			st = '\\'+'\\'.join(
				('0'+hex(ord(c))[2:])[-2:]
				for c in string.operand)
			self.text += f"@.str.{string.identifier} = constant [{l} x i8] c\"{st}\", align 1"
		for top in self.ast.tops:
			if isinstance(top, nodes.Fun):
				if top.name.operand == 'main':break
		else:assert False, "Type checker is not responding"
		main_top = top
		self.text += f"""
define i64 @main(){{;entry point
	call void @fun_{main_top.identifier}()
	ret i64 0
}}
"""
		if self.config.debug:
			self.text+=f"""
; ---------------------------
; DEBUG:
; there was {len(self.ast.tops)} tops
; constant values:
{''.join(f';	{const.name} = {const.value}{NEWLINE}' for const in self.ast.tops if isinstance(const, nodes.Const))
}; state of id counter: {id_counter}
"""
		if self.config.interpret:
			return
		with open(self.config.output_file + '.ll', 'wt', encoding='UTF-8') as file:
			file.write(self.text)
