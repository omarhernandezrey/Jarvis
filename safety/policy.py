"""
JARVIS Local - Politicas de Seguridad (Fase 2)
ActionPlan, modo simulacion, confirmacion de acciones.
"""
import enum
from dataclasses import dataclass, field
from datetime import datetime

from jarvis_local.config import get_config
from jarvis_local.safety.logger import logger
from jarvis_local.safety.secrets import redact_secrets


class RiskLevel(enum.Enum):
    NONE = 0
    READ = 1
    CREATE = 2
    EXECUTE = 3
    DELETE = 4
    CRITICAL = 5


class ActionStatus(enum.Enum):
    PLANNED = "planned"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class ActionPlan:
    action: str
    params: dict = field(default_factory=dict)
    paths_affected: list[str] = field(default_factory=list)
    risk: RiskLevel = RiskLevel.NONE
    reason: str = ""
    simulation_result: str = ""
    status: ActionStatus = ActionStatus.PLANNED
    result: str = ""
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "params": self.params,
            "paths_affected": self.paths_affected,
            "risk": self.risk.name,
            "reason": self.reason,
            "simulation_result": self.simulation_result,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    def __str__(self) -> str:
        lines = [f"ACCION: {self.action}"]
        if self.params:
            lines.append(f"  Parametros: {self.params}")
        if self.paths_affected:
            lines.append(f"  Rutas: {', '.join(self.paths_affected)}")
        lines.append(f"  Riesgo: {self.risk.name}")
        lines.append(f"  Estado: {self.status.value}")
        if self.simulation_result:
            lines.append(f"  Simulacion: {self.simulation_result}")
        if self.reason:
            lines.append(f"  Motivo: {self.reason}")
        if self.result:
            lines.append(f"  Resultado: {self.result}")
        if self.error:
            lines.append(f"  Error: {self.error}")
        return "\n".join(lines)


class SafetyPolicy:
    def __init__(self):
        cfg = get_config()
        safety_cfg = cfg.get("safety", {})
        self.simulation_mode = safety_cfg.get("simulation_mode", False)
        self.pending_plan: ActionPlan | None = None

    def is_simulation_mode(self) -> bool:
        return self.simulation_mode

    def set_simulation_mode(self, enabled: bool):
        self.simulation_mode = enabled

    def simulate(self, plan: ActionPlan) -> ActionPlan:
        """Ejecuta el plan en modo simulacion: analiza, no ejecuta."""
        plan.simulation_result = self._build_simulation_message(plan)
        plan.status = ActionStatus.PLANNED
        self._log_plan(plan)
        return plan

    def confirm(self) -> ActionPlan | None:
        """Confirma el plan pendiente si existe y es de bajo riesgo."""
        if not self.pending_plan:
            return None
        if self.pending_plan.risk.value >= RiskLevel.DELETE.value:
            self.pending_plan.status = ActionStatus.BLOCKED
            self.pending_plan.result = (
                "OPERACION BLOQUEADA: Esta accion requiere doble confirmacion "
                "que no esta disponible en esta fase."
            )
            logger.log_action(
                instruction=self.pending_plan.action,
                result=self.pending_plan.result,
                error="Requiere doble confirmacion",
            )
            plan = self.pending_plan
            self.pending_plan = None
            return plan
        self.pending_plan.status = ActionStatus.CONFIRMED
        self._log_plan(self.pending_plan, "CONFIRMADO")
        plan = self.pending_plan
        self.pending_plan = None
        return plan

    def auto_confirm(self) -> ActionPlan | None:
        """Auto-confirma para modo voz: confirma operaciones de riesgo bajo
        sin intervencion del usuario. DELETE y CRITICAL siguen bloqueados."""
        if not self.pending_plan:
            return None
        if self.pending_plan.risk.value >= RiskLevel.DELETE.value:
            self.pending_plan.status = ActionStatus.BLOCKED
            self.pending_plan.result = (
                "OPERACION BLOQUEADA: Borrado requiere confirmacion manual. "
                "Usa /confirmar en la consola."
            )
            logger.log_action(
                instruction=self.pending_plan.action,
                result=self.pending_plan.result,
                error="Auto-confirm bloqueada para DELETE",
            )
            plan = self.pending_plan
            self.pending_plan = None
            return plan
        self.pending_plan.status = ActionStatus.CONFIRMED
        self._log_plan(self.pending_plan, "AUTO-CONFIRMADO")
        plan = self.pending_plan
        self.pending_plan = None
        return plan

    def reject(self) -> ActionPlan | None:
        """Rechaza el plan pendiente."""
        if not self.pending_plan:
            return None
        self.pending_plan.status = ActionStatus.REJECTED
        self._log_plan(self.pending_plan, "RECHAZADO")
        plan = self.pending_plan
        self.pending_plan = None
        return plan

    def execute_plan(self, plan: ActionPlan, executor_fn) -> ActionPlan:
        """Ejecuta un plan usando la funcion proporcionada.
        Si no esta confirmado y no es DELETE, auto-confirma."""
        if plan.status == ActionStatus.PLANNED:
            if plan.risk.value < RiskLevel.DELETE.value:
                plan.status = ActionStatus.CONFIRMED
                self._log_plan(plan, "AUTO-CONFIRMADO-EXECUTE")
            else:
                plan.status = ActionStatus.BLOCKED
                plan.result = "El plan de borrado requiere confirmacion manual."
                return plan
        try:
            plan.result = executor_fn(plan)
            plan.status = ActionStatus.EXECUTED
        except Exception as e:
            plan.status = ActionStatus.ERROR
            redacted, _ = redact_secrets(str(e))
            plan.error = redacted
        self._log_plan(plan)
        return plan

    def block(self, reason: str) -> ActionPlan:
        """Crea un plan bloqueado por razones de seguridad."""
        plan = ActionPlan(
            action="blocked",
            risk=RiskLevel.CRITICAL,
            reason=reason,
            status=ActionStatus.BLOCKED,
            simulation_result=f"BLOQUEADO: {reason}",
        )
        self._log_plan(plan)
        return plan

    def _build_simulation_message(self, plan: ActionPlan) -> str:
        parts = [f"[SIMULACION] Se ejecutaria: {plan.action}"]
        if plan.params:
            for key, value in plan.params.items():
                parts.append(f"  {key}: {value}")
        if plan.paths_affected:
            parts.append(f"  Rutas afectadas: {', '.join(plan.paths_affected)}")
        parts.append(f"  Nivel de riesgo: {plan.risk.name}")
        parts.append("Estado: PENDIENTE DE CONFIRMACION. Usa /confirmar o /cancelar")
        return "\n".join(parts)

    def _log_plan(self, plan: ActionPlan, extra: str = ""):
        result = plan.simulation_result or plan.result or ""
        if extra:
            result = f"[{extra}] {result}"
        logger.log_action(
            instruction=plan.action,
            result=result,
            error=plan.error,
        )


policy = SafetyPolicy()
