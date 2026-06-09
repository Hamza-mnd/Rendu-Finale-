"""validators.py — Validateurs polymorphiques pour le service d'ingestion IoT.

Architecture :
  - Validator              : classe de base abstraite
  - RequiredFieldsValidator: vérifie la présence et non-vacuité des champs obligatoires
  - RangeValidator         : vérifie qu'un champ numérique est dans une plage donnée
  - ConsistencyValidator   : vérifie la cohérence entre champs (pompe / débit)
  - run_validators()       : exécute tous les validateurs et agrège les erreurs (cumulatif)

Principe : validation cumulative — toutes les erreurs sont collectées,
jamais d'arrêt à la première. Le producteur reçoit un feedback complet.
"""

from typing import List
from models import ValidationError


# ============================================================
# CLASSE DE BASE
# ============================================================
class Validator:
    """Classe de base abstraite pour tous les validateurs.

    Chaque sous-classe implémente validate() qui reçoit un dict brut
    et retourne une liste de ValidationError (vide = pas d'erreur).
    """

    def validate(self, data: dict) -> List[ValidationError]:
        """Valide data et retourne la liste des erreurs trouvées.

        Args:
            data: Dictionnaire brut représentant un SensorReading.

        Returns:
            Liste de ValidationError (vide si tout est valide).
        """
        raise NotImplementedError("Les sous-classes doivent implémenter validate()")


# ============================================================
# VALIDATEUR : CHAMPS OBLIGATOIRES
# ============================================================
class RequiredFieldsValidator(Validator):
    """Vérifie que les champs obligatoires sont présents et non vides.

    Args:
        required_fields: Liste des noms de champs obligatoires.
    """

    def __init__(self, required_fields: List[str]):
        self.required_fields = required_fields

    def validate(self, data: dict) -> List[ValidationError]:
        errors = []
        for field_name in self.required_fields:
            value = data.get(field_name)
            # Absent du dict ou None
            if value is None:
                errors.append(ValidationError(
                    field=field_name,
                    code="MISSING_FIELD",
                    message=f"Le champ '{field_name}' est obligatoire mais absent.",
                ))
            # Chaîne vide ou ne contenant que des espaces
            elif isinstance(value, str) and not value.strip():
                errors.append(ValidationError(
                    field=field_name,
                    code="EMPTY_FIELD",
                    message=f"Le champ '{field_name}' est obligatoire mais vide.",
                ))
        return errors


# ============================================================
# VALIDATEUR : PLAGE NUMÉRIQUE
# ============================================================
class RangeValidator(Validator):
    """Vérifie qu'un champ numérique est compris dans [min_val, max_val].

    Les champs None (optionnels absents) sont ignorés silencieusement.

    Args:
        field_name: Nom du champ à valider.
        min_val:    Borne inférieure inclusive.
        max_val:    Borne supérieure inclusive.
    """

    def __init__(self, field_name: str, min_val: float, max_val: float):
        self.field_name = field_name
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, data: dict) -> List[ValidationError]:
        errors = []
        value = data.get(self.field_name)

        # Champ absent ou None → ignoré (champ optionnel)
        if value is None:
            return errors

        # Tentative de conversion numérique
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            errors.append(ValidationError(
                field=self.field_name,
                code="INVALID_TYPE",
                message=(
                    f"'{self.field_name}' doit être numérique, "
                    f"reçu : {repr(value)}"
                ),
            ))
            return errors

        # Vérification de la plage
        if not (self.min_val <= numeric_value <= self.max_val):
            errors.append(ValidationError(
                field=self.field_name,
                code="OUT_OF_RANGE",
                message=(
                    f"'{self.field_name}' = {numeric_value} est hors de la plage "
                    f"[{self.min_val}, {self.max_val}]."
                ),
            ))
        return errors


# ============================================================
# VALIDATEUR : COHÉRENCE POMPE / DÉBIT
# ============================================================
class ConsistencyValidator(Validator):
    """Vérifie la cohérence entre pump_status et irrigation_l_min.

    Règle métier : si la pompe est ON, le débit doit être > 0.
    Une pompe allumée avec un débit nul signale une incohérence
    (capteur de débit HS, configuration erronée, etc.).
    """

    def validate(self, data: dict) -> List[ValidationError]:
        errors = []
        pump = str(data.get("pump_status", "")).lower()
        try:
            flow = float(data.get("irrigation_l_min", 0.0))
        except (TypeError, ValueError):
            # La cohérence ne peut pas être vérifiée si le débit est invalide
            return errors

        if pump == "on" and flow <= 0.0:
            errors.append(ValidationError(
                field="irrigation_l_min",
                code="CONSISTENCY_ERROR",
                message=(
                    "pump_status='on' mais irrigation_l_min <= 0 : "
                    "la pompe est allumée sans débit mesuré."
                ),
            ))
        return errors


# ============================================================
# FONCTION D'EXÉCUTION CUMULATIVE
# ============================================================
def run_validators(data: dict, validators: List[Validator]) -> List[ValidationError]:
    """Exécute tous les validateurs et agrège les erreurs (approche cumulative).

    Tous les validateurs sont toujours exécutés — on ne s'arrête pas
    à la première erreur. Cela permet de renvoyer un feedback complet
    au producteur en un seul aller-retour réseau.

    Args:
        data:       Dictionnaire brut représentant un SensorReading.
        validators: Liste de validateurs à appliquer.

    Returns:
        Liste agrégée de toutes les ValidationError trouvées.
    """
    all_errors: List[ValidationError] = []
    for validator in validators:
        all_errors.extend(validator.validate(data))
    return all_errors
