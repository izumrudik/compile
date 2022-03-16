from sys import implementation, stderr
import sys
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, id_counter, safe, INTRINSICS_TYPES, Type, Ptr, INT, BOOL, STR, VOID, PTR, find_fun_by_name, StructType
from dataclasses import dataclass
__INTRINSICS_IMPLEMENTATION:'dict[str,str]' = {
	'exit':"declare void @exit(i64)\n"
}

INTRINSICS_IMPLEMENTATION:'dict[int,tuple[str,str]]' = {
	INTRINSICS_TYPES[name][2]:(name,__INTRINSICS_IMPLEMENTATION[name]) for name in __INTRINSICS_IMPLEMENTATION
}
@dataclass
class TV:#typed value
	typ:'Type|None'  = None
	val:'str' = ''
	def __str__(self) -> str:
		if typ is None:
			return f"<None TV>"
		return f"{self.typ.llvm} {self.val}"
class GenerateAssembly:
	__slots__ = ('text','ast','config', 'variables', 'funs')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.config   :Config                    = config
		self.ast      :nodes.Tops                = ast
		self.text     :str                       = ''
		self.variables:list[nodes.TypedVariable] = []
		self.funs     :list[nodes.Fun]           = []
		self.generate_assembly()
	def visit_fun(self, node:nodes.Fun) -> TV:
		self.funs.append(node)
		assert self.variables == [], f"visit_fun called with {[str(var) for var in self.variables]} (vars should be on the stack) at {node}"
		self.variables = node.arg_types.copy()
		ot = node.output_type
		self.text += f"""
define {ot.llvm} @fun_{node.identifier}\
({', '.join(f'{arg.typ.llvm} %{arg.identifier}' for arg in node.arg_types)}) {{
{f'	%retvar = alloca {ot.llvm}, align 4{NEWLINE}' if ot != VOID else ''}"""
		self.visit(node.code)


		self.text += f"""\
{f'	br label %return' if ot == VOID else 'unreachable'}		
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
			name = f"@{node.name.operand}"
		else:
			for fun in self.funs:
				if fun.name == node.name:
					rt = fun.output_type
					name = f"@fun_{fun.identifier}"
					break
			else:	
				print(f"ERROR: {node.name.loc}: did not find function '{node.name}'", file=stderr)
				sys.exit(54)
		if rt != VOID:
			self.text+=f"""\
	%c{node.identifier} = """		
		self.text += f"""\
call {rt.llvm} {name}({', '.join(args)})
"""
		if rt != VOID:
			return TV(rt, f"%c{node.identifier}")
		return TV(VOID)
	def visit_token(self, token:Token) -> TV:
		if token.typ == TT.DIGIT:
			return TV(INT, token.operand)
		elif token.typ == TT.STRING:
			assert False, "strings are not implemented"
		else:
			assert False, f"Unreachable: {token.typ=}"
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> TV:
		...
	def visit_expr_state(self, node:nodes.ExprStatement) -> TV:
		self.visit(node.value)
		return TV()
	def visit_assignment(self, node:nodes.Assignment) -> TV:
		assert False, 'visit_assignment is not implemented yet'
	def visit_refer(self, node:nodes.ReferTo) -> TV:
		assert False, 'visit_refer is not implemented yet'
	def visit_defining(self, node:nodes.Defining) -> TV:
		assert False, 'visit_defining is not implemented yet'
	def visit_reassignment(self, node:nodes.ReAssignment) -> TV:
		assert False, 'visit_reassignment is not implemented yet'
	def visit_if(self, node:nodes.If) -> TV:
		assert False, 'visit_if is not implemented yet'
	def visit_while(self, node:nodes.While) -> TV:
		assert False, 'visit_while is not implemented yet'
	def visit_intr_constant(self, node:nodes.IntrinsicConstant) -> TV:
		assert False, 'visit_intr_constant is not implemented yet'
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
		assert False, 'visit_cast is not implemented yet'
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
		for top in self.ast.tops:
			if isinstance(top, nodes.Fun):
				if top.name.operand == 'main':break
		else:assert False, "Type checker is not responding"
		main_top = top
		self.text += f"""
define i32 @main(){{;entry point
	call void @fun_{main_top.identifier}()
	ret i32 0
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
		with open(self.config.output_file + '.ll', 'wt', encoding='UTF-8') as file:
			file.write(self.text)