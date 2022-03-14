import sys
from sys import stderr

from .primitives import nodes, Node, Token, TT, Config, INTRINSICS_TYPES, find_fun_by_name, Type, Ptr, INT, BOOL, STR, VOID, PTR, StructType

class TypeCheck:
	__slots__ = ('config', 'ast', 'variables', 'expected_return_type')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.ast = ast
		self.config = config
		self.variables:dict[str, Type] = {}
		self.expected_return_type:Type = VOID
		for top in ast.tops:
			self.check(top)
		for top in ast.tops:
			if isinstance(top, nodes.Fun):
				if top.name.operand == 'main':
					if top.output_type != VOID:
						print(f"ERROR: {top.name.loc}: entry point (function 'main') has to return nothing, found {top.output_type}", file=stderr)
						sys.exit(26)
					if len(top.arg_types) != 0:
						print(f"ERROR: {top.name.loc}: entry point (function 'main') has to take no arguments", file=stderr)
						sys.exit(27)
					break
		else:
			print("ERROR: did not find entry point (function 'main')", file=stderr)
			sys.exit(28)
	def check_fun(self, node:nodes.Fun) -> Type:
		vars_before = self.variables.copy()
		self.variables.update({arg.name.operand:arg.typ for arg in node.arg_types})
		self.expected_return_type = node.output_type	
		ret_typ = self.check(node.code)
		if node.output_type != ret_typ:
			print(f"ERROR: {node.name.loc}: specified return type ({node.output_type}) does not match actual return type ({ret_typ})", file=stderr)
			sys.exit(29)
		self.variables = vars_before
		self.expected_return_type = VOID
		return VOID
	def check_code(self, node:nodes.Code) -> Type:
		vars_before = self.variables.copy()
		ret = None
		for statement in node.statements:
			if isinstance(statement,nodes.Return):
				if ret is None:
					ret = self.check(statement)
			self.check(statement)
		self.variables = vars_before #this is scoping
		if ret is None:
			return VOID
		return self.expected_return_type
	def check_function_call(self, node:nodes.FunctionCall) -> Type:
		intrinsic = INTRINSICS_TYPES.get(node.name.operand)
		if intrinsic is not None:
			input_types, output_type, _ = intrinsic
		else:
			found_node = find_fun_by_name(self.ast, node.name)
			input_types, output_type = [t.typ for t in found_node.arg_types], found_node.output_type
		if len(input_types) != len(node.args):
			print(f"ERROR: {node.name.loc}: function '{node.name}' accepts {len(input_types)} arguments, provided {len(node.args)}", file=stderr)
			sys.exit(30)
		for idx, arg in enumerate(node.args):
			typ = self.check(arg)
			needed = input_types[idx]
			if typ != needed:
				print(f"ERROR: {node.name.loc}: argument {idx} has incompatible type '{typ}', expected '{needed}'", file=stderr)
				sys.exit(31)
		return output_type
	def check_bin_exp(self, node:nodes.BinaryExpression) -> Type:
		left = self.check(node.left)
		right = self.check(node.right)
		return node.typ(left,right)
	def check_expr_state(self, node:nodes.ExprStatement) -> Type:
		self.check(node.value)
		return VOID
	def check_token(self, token:Token) -> Type:
		if   token == TT.STRING : return STR
		elif token == TT.DIGIT  : return INT
		else:
			assert False, f"unreachable {token.typ=} {token=} {token.loc = !s}"
	def check_assignment(self, node:nodes.Assignment) -> Type:
		actual_type = self.check(node.value)
		if node.var.typ != actual_type:
			print(f"ERROR: {node.var.name.loc}: specified type '{node.var.typ}' does not match actual type '{actual_type}' in variable assignment", file=stderr)
			sys.exit(32)
		self.variables[node.var.name.operand] = node.var.typ
		return VOID
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.variables.get(node.name.operand)
		if typ is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}'", file=stderr)
			sys.exit(33)
		return typ
	def check_defining(self, node:nodes.Defining) -> Type:
		self.variables[node.var.name.operand] = node.var.typ
		return VOID
	def check_reassignment(self, node:nodes.ReAssignment) -> Type:
		actual = self.check(node.value)

		specified = self.variables.get(node.name.operand)
		if specified is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}' (specify type to make new)", file=stderr)
			sys.exit(34)
		if actual != specified:
			print(f"ERROR: {node.name.loc}: variable type ({specified}) does not match type provided ({actual}), to override specify type", file=stderr)
			sys.exit(35)
		return VOID
	def check_if(self, node:nodes.If) -> Type:
		actual = self.check(node.condition)
		if actual != BOOL:
			print(f"ERROR: {node.loc}: if statement expected {BOOL} value, got {actual}", file=stderr)
			sys.exit(36)
		if node.else_code is None:
			return self.check(node.code) #@return
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code) #@return
		if actual_if != actual_else:
			print(f"ERROR: {node.loc}: one branch return's while another does not (tip:refactor without 'else')",file=stderr)
			sys.exit(37)
		return actual_if

	def check_while(self, node:nodes.While) -> Type:
		actual = self.check(node.condition)
		if actual != BOOL:
			print(f"ERROR: {node.loc}: while statement expected {BOOL} value, got {actual}", file=stderr)
			sys.exit(38)
		return self.check(node.code)
		
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		return node.typ(self.check(node.left))
	def check_intr_constant(self, node:nodes.IntrinsicConstant) -> Type:
		return node.typ
	
	def check_memo(self, node:nodes.Memo) -> Type:
		self.variables[node.name.operand] = PTR
		return VOID
	def check_var(self, node:nodes.Var) -> Type:
		self.variables[node.name.operand] = Ptr(node.typ)
		return VOID
	def check_const(self, node:nodes.Const) -> Type:
		self.variables[node.name.operand] = INT
		return VOID
	def check_struct(self, node:nodes.Struct) -> Type:
		return VOID
	
	def check_return(self, node:nodes.Return) -> Type:
		ret = self.check(node.value)
		if ret != self.expected_return_type:
			print(f"ERROR: {node.loc}: actual return type ({ret}) does not match expected return type ({self.expected_return_type})",file=stderr)
			sys.exit(39)
		return ret
	def check_dot(self, node:nodes.Dot) -> Type:
		left = self.check(node.origin)
		if not isinstance(left,Ptr):
			print(f"ERROR: {node.loc}: trying to access fields not of the struct",file=stderr)
			sys.exit(40)
		pointed = left.pointed
		if isinstance(pointed, StructType):	return Ptr(node.lookup_struct(pointed.struct)[1])
		else:
			assert False, f'unreachable, unknown {type(left.pointed) = }'
	def check_cast(self, node:nodes.Cast) -> Type:
		left = self.check(node.value)
		if int(node.typ) != int(left):
			print(f"ERROR: {node.loc}: trying to cast type '{left}' with size {int(left)} to type '{node.typ}' with size {int(node.typ)}",file=stderr)
			sys.exit(41)
		return node.typ
	def check(self, node:'Node|Token') -> Type:
		if   type(node) == nodes.Fun              : return self.check_fun           (node)
		elif type(node) == nodes.Memo             : return self.check_memo          (node)
		elif type(node) == nodes.Var              : return self.check_var           (node)
		elif type(node) == nodes.Const            : return self.check_const         (node)
		elif type(node) == nodes.Struct           : return self.check_struct        (node)
		elif type(node) == nodes.Code             : return self.check_code          (node)
		elif type(node) == nodes.FunctionCall     : return self.check_function_call (node)
		elif type(node) == nodes.BinaryExpression : return self.check_bin_exp       (node)
		elif type(node) == nodes.UnaryExpression  : return self.check_unary_exp     (node)
		elif type(node) == nodes.IntrinsicConstant: return self.check_intr_constant (node)
		elif type(node) == nodes.ExprStatement    : return self.check_expr_state    (node)
		elif type(node) == nodes.Assignment       : return self.check_assignment    (node)
		elif type(node) == nodes.ReferTo          : return self.check_refer         (node)
		elif type(node) == nodes.Defining         : return self.check_defining      (node)
		elif type(node) == nodes.ReAssignment     : return self.check_reassignment  (node)
		elif type(node) == nodes.If               : return self.check_if            (node)
		elif type(node) == nodes.While            : return self.check_while         (node)
		elif type(node) == nodes.Return           : return self.check_return        (node)
		elif type(node) == nodes.Dot              : return self.check_dot           (node)
		elif type(node) == nodes.Cast             : return self.check_cast          (node)
		elif type(node) == Token                  : return self.check_token         (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
