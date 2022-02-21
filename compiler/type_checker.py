import sys
from sys import stderr

from .primitives import nodes, Node, Type, Token, TT, Config

from compiler.generator import INTRINSICS, find_fun_by_name

class TypeCheck:
	__slots__ = ('config', 'ast', 'variables')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.ast = ast
		self.config = config
		self.variables:dict[Token, Type] = {}
		for top in ast.tops:
			self.check(top)
	def check_fun(self, node:nodes.Fun) -> Type:
		vars_before = self.variables.copy()
		self.variables.update({arg.name:arg.typ for arg in node.arg_types})
		ret_typ = self.check(node.code)
		if node.output_type != ret_typ:
			print(f"ERROR: {node.name.loc}: specified return type ({node.output_type}) does not match actual return type ({ret_typ})", file=stderr)
			sys.exit(16)
		self.variables = vars_before
		return Type.VOID
	def check_code(self, node:nodes.Code) -> Type:
		vars_before = self.variables.copy()
		ret = Type.VOID
		for statement in node.statements:
			#@return
			self.check(statement)
		self.variables = vars_before #this is scoping
		return ret
	def check_function_call(self, node:nodes.FunctionCall) -> Type:
		intrinsic = INTRINSICS.get(node.name.operand)
		if intrinsic is not None:
			_, input_types, output_type, _ = intrinsic
		else:
			found_node = find_fun_by_name(self.ast, node.name)
			input_types, output_type = [t.typ for t in found_node.arg_types], found_node.output_type
		if len(input_types) != len(node.args):
			print(f"ERROR: {node.name.loc}: function '{node.name}' accepts {len(input_types)} arguments, provided {len(node.args)}", file=stderr)
			sys.exit(17)
		for idx, arg in enumerate(node.args):
			typ = self.check(arg)
			needed = input_types[idx]
			if typ != needed:
				print(f"ERROR: {node.name.loc}: argument {idx} has incompatible type '{typ}', expected '{needed}'", file=stderr)
				sys.exit(18)
		return output_type
	def check_bin_exp(self, node:nodes.BinaryExpression) -> Type:
		left = self.check(node.left)
		right = self.check(node.right)
		return node.typ(left,right)
	def check_expr_state(self, node:nodes.ExprStatement) -> Type:
		self.check(node.value)
		return Type.VOID
	def check_token(self, token:Token) -> Type:
		if   token == TT.STRING : return Type.STR
		elif token == TT.DIGIT  : return Type.INT
		else:
			assert False, f"unreachable {token.typ=}"
	def check_assignment(self, node:nodes.Assignment) -> Type:
		actual_type = self.check(node.value)
		if node.var.typ != actual_type:
			print(f"ERROR: {node.var.name.loc}: specified type '{node.var.typ}' does not match actual type '{actual_type}' ", file=stderr)
			sys.exit(20)
		self.variables[node.var.name] = node.var.typ
		return Type.VOID
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.variables.get(node.name)
		if typ is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}'", file=stderr)
			sys.exit(21)
		return typ
	def check_defining(self, node:nodes.Defining) -> Type:
		self.variables[node.var.name] = node.var.typ
		return Type.VOID
	def check_reassignment(self, node:nodes.ReAssignment) -> Type:
		actual = self.check(node.value)

		specified = self.variables.get(node.name)
		if specified is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}' (specify type to make new)", file=stderr)
			sys.exit(22)
		if actual != specified:
			print(f"ERROR: {node.name.loc}: variable type ({specified}) does not match type provided ({actual}), to override specify type", file=stderr)
			sys.exit(23)
		return Type.VOID
	def check_if(self, node:nodes.If) -> Type:
		actual = self.check(node.condition)
		if actual != Type.BOOL:
			print(f"ERROR: {node.loc}: if statement expected {Type.BOOL} value, got {actual}", file=stderr)
			sys.exit(24)
		if node.else_code is None:
			return self.check(node.code) #@return
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code) #@return
		assert actual_if == actual_else, "If has incompatible branches error is not written (and should not be possible)"
		return actual_if
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		def unary_op(input_type:Type ) -> Type:
			right = self.check(node.right)
			if input_type == right:
				return node.typ
			print(f"ERROR: {node.operation.loc}: unsupported operation '{node.operation}' for '{right}'", file=stderr)
			sys.exit(25)
		if node.operation == TT.NOT: return unary_op(Type.BOOL)
		else:
			assert False, f"Unreachable, {node.operation=}"
	def check_intr_constant(self, node:nodes.IntrinsicConstant) -> Type:
		return node.typ
	
	def check_memo(self, node:nodes.Memo) -> Type:
		self.variables[node.name] = Type.PTR
		return Type.VOID
	def check_const(self, node:nodes.Const) -> Type:
		self.variables[node.name] = Type.INT
		return Type.VOID

	def check(self, node:'Node|Token') -> Type:
		if   type(node) == nodes.Fun              : return self.check_fun           (node)
		elif type(node) == nodes.Memo             : return self.check_memo          (node)
		elif type(node) == nodes.Const            : return self.check_const         (node)
		elif type(node) == nodes.Code             : return self.check_code          (node)
		elif type(node) == nodes.FunctionCall     : return self.check_function_call (node)
		elif type(node) == nodes.BinaryExpression : return self.check_bin_exp       (node)
		elif type(node) == nodes.UnaryExpression  : return self.check_unary_exp     (node)
		elif type(node) == nodes.IntrinsicConstant: return self.check_intr_constant (node)
		elif type(node) == nodes.ExprStatement    : return self.check_expr_state    (node)
		elif type(node) == Token                  : return self.check_token         (node)
		elif type(node) == nodes.Assignment       : return self.check_assignment    (node)
		elif type(node) == nodes.ReferTo          : return self.check_refer         (node)
		elif type(node) == nodes.Defining         : return self.check_defining      (node)
		elif type(node) == nodes.ReAssignment     : return self.check_reassignment  (node)
		elif type(node) == nodes.If               : return self.check_if            (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
