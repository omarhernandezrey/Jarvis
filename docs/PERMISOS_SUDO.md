# Permisos y sudo — FASE E · E2

## El modelo, en una frase

| Nivel de riesgo del contrato | Qué hace JARVIS |
| --- | --- |
| `READ` (`NONE`) | ejecuta sin preguntar |
| `CREATE`, `EXECUTE` | ejecuta y **verifica** el efecto (D1) |
| `DELETE`, `CRITICAL` | **pide confirmación** mostrando qué y sobre qué, con `/cancelar`; luego ejecuta y verifica |

Todo pasa por la auditoría append-only de D2 (`logs/audit.jsonl`).

## Sudo: nunca implícito

**JARVIS no invoca `sudo` jamás.** Si una acción necesitaría root, la
**bloquea** (`safety/permisos.bloqueo_por_sudo`) y te entrega la regla de
sudoers concreta más la alternativa manual. Tú decides si la habilitas.

### Cuándo aparece

| Acción (oleada) | ¿Necesita root? |
| --- | --- |
| Matar un proceso **tuyo** (E3) | No — `kill` normal |
| Matar un proceso de **otro usuario** o de `root` (E3) | Sí → BLOQUEADO, sin regla: hazlo tú con `sudo kill <PID>` |
| Estado/parar/arrancar/reiniciar una unidad **`--user`** (E4) | No |
| Lo mismo sobre una unidad de **sistema** (E4) | Sí → BLOQUEADO con la regla de abajo |

### La regla, si decides habilitarla

Edita **por unidad concreta**, nunca en bloque (un `NOPASSWD` a
`systemctl *` es un agujero de seguridad):

```
sudo visudo -f /etc/sudoers.d/jarvis
```

```
# Sustituye <UNIDAD> por la unidad exacta, p. ej. cups.service
%sudo ALL=(root) NOPASSWD: /usr/bin/systemctl start <UNIDAD>, \
                           /usr/bin/systemctl stop <UNIDAD>, \
                           /usr/bin/systemctl restart <UNIDAD>
```

Aun con la regla puesta, **E1 (lista de intocables) sigue mandando**: JARVIS
no parará `NetworkManager`, `gdm`, `systemd-logind`, etc. ni aunque se lo
pidas y tengas la regla.

## Auditoría

Cada acción de escritura / destructiva / de sistema —y cada bloqueo por sudo—
queda en `logs/audit.jsonl` con herramienta, parámetros, resultado de VERIFY y
si hubo confirmación. Consultable: *"qué hiciste hoy"*, *"qué cambiaste ayer"*.
