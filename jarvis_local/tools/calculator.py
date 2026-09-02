"""
JARVIS Local - Calculadora (Fase 4)
Evalua expresiones matematicas de forma SEGURA (AST, sin eval directo).
Soporta lenguaje natural: "cuanto es 5 mas 3 por 2".
"""
import ast
import math
import operator
import re

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}

# Sin limites, "factorial de 999999999" o "2 elevado a 999999999" cuelgan
# el proceso de verdad calculando un entero de millones de digitos (no es
# teorico: probado, tarda mas de 8s y sigue subiendo memoria). El AST ya
# impide ejecutar codigo arbitrario; esto impide DoS con codigo permitido.
_MAX_FACTORIAL = 10000    # 10000! ya tiene ~35660 digitos
_MAX_EXPONENT = 1000


class _NumeroDemasiadoGrande(ValueError):
    """Distinta de un ValueError generico para no confundirla con
    'expresion no permitida' (esa si debe quedar como error generico:
    no queremos mostrarle al usuario el dump interno del AST)."""


def _bounded_factorial(n):
    if abs(n) > _MAX_FACTORIAL:
        raise _NumeroDemasiadoGrande(
            f"El factorial es demasiado grande para calcularlo (maximo {_MAX_FACTORIAL}).")
    return math.factorial(n)


_FUNCS = {
    "raiz": math.sqrt, "sqrt": math.sqrt, "abs": abs, "redondear": round,
    "round": round, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "factorial": _bounded_factorial,
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
    ("al cubo", "** 3"), ("al cuadrado", "** 2"),
    ("mas", "+"), ("menos", "-"), ("por", "*"), ("multiplicado por", "*"),
    ("dividido entre", "/"), ("dividido por", "/"), ("entre", "/"),
    ("sobre", "/"), ("modulo", "%"), ("x", "*"),
    ("por ciento de", "/100*"), ("por ciento", "/100"),
    ("raiz cuadrada de", "raiz"),
], key=lambda par: -len(par[0].split()))


# Palabras que la gente intercala al dictar ("el 15 por ciento de 2000",
# "cuanto es la raiz de 144", "factorial de 5"). Se descartan solo si ninguna
# frase de _WORDS las consumio antes.
_FILLERS = {"el", "la", "los", "las", "un", "una",
            "de", "cuanto", "cuantos", "cuanta", "cuantas", "es", "son", "da",
            "cual", "vale", "oye", "resultado", "dame"}


def normalize_expression(text: str) -> str:
    """Convierte expresion en lenguaje natural a expresion matematica."""
    t = text.lower().strip()
    for k, v in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                 "¿": "", "?": "", "¡": "", "!": "", ",": ".", "=": ""}.items():
        t = t.replace(k, v)
    # porcentajes con el simbolo %: "20% de 350" -> "(20/100)* 350",
    # "20%" a secas -> "(20/100)". (Antes: SyntaxError; % es modulo en Python.)
    t = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*de\b', r'(\1/100)* ', t)
    t = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1/100)', t)
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
            if tokens[i] not in _FILLERS:
                out.append(tokens[i])
            i += 1
    expr = " ".join(out)
    # "raiz 25" -> "raiz(25)" para funciones dichas en lenguaje natural.
    # "de"/"cuadrada" ya se descartaron como fillers, asi que aqui "raiz de
    # 144" y "factorial de 5" ya llegan como "raiz 144" / "factorial 5".
    expr = re.sub(r'\b(raiz|sqrt|factorial|abs|log|log10|ln)\s+\(?([\d.]+)\)?',
                   r'\1(\2)', expr)
    expr = expr.replace("ln(", "log(")
    return expr


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT and abs(left) > 1:
            raise _NumeroDemasiadoGrande(
                f"Ese exponente es demasiado grande para calcularlo (maximo {_MAX_EXPONENT}).")
        return _OPS[type(node.op)](left, right)
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


_RE_INCOGNITA = re.compile(r'(?<![a-z])([a-z])(?![a-z(])')


def _es_ecuacion(expression: str) -> bool:
    """Hay un '=' real (no '<='/'>=') y una incognita de una letra."""
    t = expression.lower().replace("<=", "").replace(">=", "").replace("!=", "")
    if "=" not in t:
        return False
    candidatos = set(_RE_INCOGNITA.findall(t)) - set(_FUNCS) - set(_CONSTS) - {"x"}
    return "x" in _RE_INCOGNITA.findall(t) or bool(candidatos)


def _solve_lineal(expression: str) -> tuple[str, float] | None:
    """Resuelve una ecuacion LINEAL de una incognita evaluando f(x)=LHS-RHS en
    tres puntos. Devuelve (incognita, valor) o None si no es lineal / no aplica.
    """
    raw = expression.lower().strip()
    raw = re.sub(r'^\s*(?:resuelve|resolver|despeja(?:me)?|despejar|halla|calcula)\s+', '', raw)
    raw = re.sub(r'^\s*([a-z])\s+(?:en|de|para|:)\s+', r'', raw)   # "x en 2x+4=10"
    for bad in ("<=", ">=", "!="):
        raw = raw.replace(bad, "")
    if raw.count("=") != 1:
        return None
    lhs, rhs = raw.split("=")
    letras = (set(_RE_INCOGNITA.findall(lhs)) | set(_RE_INCOGNITA.findall(rhs)))
    letras -= set(_FUNCS) | set(_CONSTS)
    if len(letras) != 1:
        return None
    var = letras.pop()

    def _lado(txt: str, val: float) -> float:
        # "2x" -> "2*x", "x2" -> "x*2", luego sustituir la incognita por el valor
        s = re.sub(r'(\d)\s*' + var + r'\b', r'\1*' + var, txt)
        s = re.sub(r'\b' + var + r'\s*(\d)', var + r'*\1', s)
        s = re.sub(r'\b' + var + r'\b', f'({val})', s)
        return evaluate(s)

    try:
        f0 = _lado(lhs, 0.0) - _lado(rhs, 0.0)
        f1 = _lado(lhs, 1.0) - _lado(rhs, 1.0)
        f2 = _lado(lhs, 2.0) - _lado(rhs, 2.0)
    except Exception:
        return None
    m = f1 - f0
    if abs((f2 - f0) - 2 * m) > 1e-9:          # no es lineal
        return None
    if abs(m) < 1e-12:                          # sin solucion unica
        return None
    return var, -f0 / m


def calculate(expression: str) -> ActionPlan:
    plan = ActionPlan(action="calcular", params={"expresion": expression},
                      risk=RiskLevel.READ, reason="Calculo matematico local")

    # --- ECUACION LINEAL DE UNA INCOGNITA ---
    if _es_ecuacion(expression):
        sol = _solve_lineal(expression)
        if sol is not None:
            var, val = sol
            val = int(val) if abs(val - round(val)) < 1e-9 else round(val, 6)
            plan.result = f"{var} = {val}, senor."
            plan.status = ActionStatus.EXECUTED
        else:
            plan.status = ActionStatus.ERROR
            plan.result = ("Esa ecuacion no la puedo resolver localmente, senor "
                           "(solo lineales de una incognita). Pruebe con "
                           "'pregunta a wolfram ...'.")
        return plan

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
    except _NumeroDemasiadoGrande as e:
        plan.status = ActionStatus.ERROR
        plan.result = f"{e} senor."
    except Exception:
        plan.status = ActionStatus.ERROR
        plan.result = (f"No pude interpretar la expresion '{expression}'. "
                       "Intente algo como: calcula 5 mas 3 por 2.")
    return plan
