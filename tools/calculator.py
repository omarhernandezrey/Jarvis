"""
JARVIS Local - Calculadora (Fase 4)
Evalua expresiones matematicas de forma SEGURA (AST, sin eval directo).
Soporta lenguaje natural: "cuanto es 5 mas 3 por 2".
"""
import ast
import math
import operator

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}

_FUNCS = {
    "raiz": math.sqrt, "sqrt": math.sqrt, "abs": abs, "redondear": round,
    "round": round, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "factorial": math.factorial,
}

_CONSTS = {"pi": math.pi, "e": math.e}

# Palabras en espanol -> operadores. Ordenado por cantidad de palabras de
# la frase, DESCENDENTE (la mas larga primero): normalize_expression()
# usa el primer match que encuentra recorriendo esta lista en orden, asi
# que si "por" (1 palabra) va antes que "por ciento de" (3 palabras), esta
# ultima nunca se alcanza a evaluar -- "50 por ciento de 200" se leia
# "50 * ciento de 200" (invalido) en vez de "50 /100*200" (=100). Ordenar
# por longitud evita que un futuro agregado reintroduzca el mismo bug.
_WORDS = sorted([
    ("elevado a la", "**"), ("elevado a", "**"), ("a la potencia", "**"),
    ("mas", "+"), ("menos", "-"), ("por", "*"), ("multiplicado por", "*"),
    ("dividido entre", "/"), ("dividido por", "/"), ("entre", "/"),
    ("sobre", "/"), ("modulo", "%"), ("x", "*"),
    ("por ciento de", "/100*"), ("raiz cuadrada de", "raiz"),
], key=lambda par: -len(par[0].split()))


def normalize_expression(text: str) -> str:
    """Convierte expresion en lenguaje natural a expresion matematica."""
    t = text.lower().strip()
    for k, v in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                 "¿": "", "?": "", "¡": "", "!": "", ",": ".", "=": ""}.items():
        t = t.replace(k, v)
    # solo reemplazar palabras completas
    tokens = t.split()
    out = []
    i = 0
    while i < len(tokens):
        matched = False
        for words, op in _WORDS:
            wlist = words.split()
            if tokens[i:i + len(wlist)] == wlist:
                out.append(op)
                i += len(wlist)
                matched = True
                break
        if not matched:
            out.append(tokens[i])
            i += 1
    expr = " ".join(out)
    # "raiz 25" -> "raiz(25)" para funciones dichas en lenguaje natural
    import re as _re
    expr = _re.sub(r'\b(raiz|sqrt|factorial|abs)\s+([\d.]+)', r'\1(\2)', expr)
    return expr


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS and not node.keywords:
        args = [_safe_eval(a) for a in node.args]
        return _FUNCS[node.func.id](*args)
    raise ValueError(f"Expresion no permitida: {ast.dump(node)[:60]}")


def evaluate(expression: str) -> float:
    """Evalua una expresion matematica de forma segura."""
    expr = normalize_expression(expression)
    tree = ast.parse(expr, mode="eval")
    return _safe_eval(tree)


def calculate(expression: str) -> ActionPlan:
    plan = ActionPlan(action="calcular", params={"expresion": expression},
                      risk=RiskLevel.READ, reason="Calculo matematico local")
    try:
        result = evaluate(expression)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        elif isinstance(result, float):
            result = round(result, 6)
        plan.result = f"El resultado es {result}, senor."
        plan.status = ActionStatus.EXECUTED
    except ZeroDivisionError:
        plan.status = ActionStatus.ERROR
        plan.result = "No es posible dividir entre cero, senor."
    except Exception:
        plan.status = ActionStatus.ERROR
        plan.result = (f"No pude interpretar la expresion '{expression}'. "
                       "Intente algo como: calcula 5 mas 3 por 2.")
    return plan
