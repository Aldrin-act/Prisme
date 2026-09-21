"""Calendrier ouvré d'un atelier en mode heures : quels instants sont travaillables, et où finit
réellement une opération qui traverse la nuit ou un week-end.

Règle métier (une seule, partagée par le solveur généré, le garde-fou de faisabilité, la correction
post-solveur et les métriques) : **une opération ne travaille que pendant les heures ouvrées**. Elle
peut démarrer à 19h, travailler jusqu'à 22h, s'arrêter, puis reprendre le lendemain à 8h — sa `duree`
compte les heures *travaillées*, jamais les heures fermées traversées. Sa fin réelle est donc
`fin_calendaire(instance, debut, duree)`, et non plus `debut + duree`.

Le calendrier n'existe que si l'instance est en mode `"heures"` **et** porte `position_zero_semaine`
(position de l'instant 0 dans la semaine, voir `InstanceTRCO`). Sans cela — cas de toute instance en
jours, de tout ingest, du banc synthétique — rien ne change : `fin_calendaire == debut + duree`.
`position_zero_semaine` est posée par l'exécution (`sandbox/runner.py`) à partir de l'instant réel de
l'exécution : elle ne fait jamais partie de l'instance enregistrée.

Arithmétique entière pure, sans `datetime` : importable telle quelle dans un solveur généré
(`from dsl.calendrier import fin_calendaire, premier_instant_ouvert`).
"""

from __future__ import annotations

from datetime import datetime

from dsl.schema import InstanceTRCO

CYCLE_HEURES = 168  # 7 jours × 24 h — même cycle que `ContrainteDisponibiliteRessource`


def position_zero_depuis(moment: datetime) -> int:
    """Position dans la semaine (0 = dimanche 00h, 167 = samedi 23h) de l'heure de `moment` —
    même convention que `InstanceTRCO.jours_fermes` (0 = dimanche)."""
    return (moment.isoweekday() % 7) * 24 + moment.hour


def avec_calendrier(instance: InstanceTRCO, moment: datetime) -> InstanceTRCO:
    """Copie de `instance` dont l'instant 0 est ancré sur `moment` (heure locale de l'atelier) — sans
    effet en mode jours. Ne mute jamais l'instance reçue."""
    if instance.unite_temps != "heures":
        return instance
    return instance.model_copy(update={"position_zero_semaine": position_zero_depuis(moment)})


def calendrier_actif(instance: InstanceTRCO) -> bool:
    return instance.unite_temps == "heures" and instance.position_zero_semaine is not None


def est_instant_ouvre(instance: InstanceTRCO, instant: int) -> bool:
    """`True` si l'heure `[instant, instant+1[` est travaillable. Toujours vrai sans calendrier."""
    if not calendrier_actif(instance):
        return True
    position = (instance.position_zero_semaine + instant) % CYCLE_HEURES
    jour, heure = divmod(position, 24)
    return jour not in instance.jours_fermes and instance.heure_ouverture <= heure < instance.heure_fermeture


def _aucune_heure_ouvree(instance: InstanceTRCO) -> bool:
    return not any(est_instant_ouvre(instance, i) for i in range(CYCLE_HEURES))


def premier_instant_ouvert(instance: InstanceTRCO, instant: int) -> int:
    """Plus petit `t >= instant` dont l'heure est ouvrée — `instant` lui-même s'il l'est déjà."""
    if not calendrier_actif(instance) or _aucune_heure_ouvree(instance):
        return instant
    while not est_instant_ouvre(instance, instant):
        instant += 1
    return instant


def fin_calendaire(instance: InstanceTRCO, debut: int, duree: int) -> int:
    """Instant qui suit la dernière heure travaillée d'une opération de `duree` heures de travail
    démarrant à `debut` : les heures fermées sont traversées sans être comptées. Une opération qui
    démarre à une heure fermée commence à travailler à la première heure ouvrée suivante."""
    if not calendrier_actif(instance) or _aucune_heure_ouvree(instance) or duree <= 0:
        return debut + duree
    instant = premier_instant_ouvert(instance, debut)
    restant = duree
    while restant > 0:
        if est_instant_ouvre(instance, instant):
            restant -= 1
        instant += 1
    return instant


def segments_travailles(instance: InstanceTRCO, debut: int, duree: int) -> list[tuple[int, int]]:
    """Plages `[début, fin[` réellement travaillées d'une opération (une par jour ouvré traversé) —
    ce que le Gantt dessine. Sans calendrier : une seule plage `[debut, debut+duree[`."""
    if not calendrier_actif(instance) or _aucune_heure_ouvree(instance) or duree <= 0:
        return [(debut, debut + duree)]
    segments: list[tuple[int, int]] = []
    instant = premier_instant_ouvert(instance, debut)
    restant = duree
    while restant > 0:
        if est_instant_ouvre(instance, instant):
            if segments and segments[-1][1] == instant:
                segments[-1] = (segments[-1][0], instant + 1)
            else:
                segments.append((instant, instant + 1))
            restant -= 1
        instant += 1
    return segments
