# allows for arithmetic expressions in XML files, e.g. 2*796020.0

import ast
import operator as op

operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

def eval_expr(expr):
    def _eval(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Only numbers are allowed: {expr}")

        if isinstance(node, ast.BinOp):
            if type(node.op) not in operators:
                raise ValueError(f"Unsupported operator in expression: {expr}")
            return operators[type(node.op)](_eval(node.left), _eval(node.right))

        if isinstance(node, ast.UnaryOp):
            if type(node.op) not in operators:
                raise ValueError(f"Unsupported operator in expression: {expr}")
            return operators[type(node.op)](_eval(node.operand))

        raise ValueError(f"Unsupported expression: {expr}")

    return float(_eval(ast.parse(expr.strip(), mode="eval").body))
