"""router.py — Registry de méthodes RPC et dispatch (Séance 4)."""


class MethodRouter:
    """Registre de méthodes RPC avec dispatch.

    Pattern Open/Closed : pour ajouter une méthode, on enregistre
    une fonction — aucune modification du handler HTTP nécessaire.
    """

    def __init__(self):
        self._registry: dict[str, callable] = {}

    def register(self, method_name: str, func: callable) -> None:
        """Enregistre une fonction pour un nom de méthode.

        Raises:
            ValueError: si le nom est déjà enregistré.
        """
        if method_name in self._registry:
            raise ValueError(f"Méthode déjà enregistrée : {method_name}")
        self._registry[method_name] = func

    def dispatch(self, method_name: str, params: dict):
        """Route l'appel vers la fonction enregistrée.

        Raises:
            KeyError: si la méthode est inconnue.
            Exception: toute exception levée par la fonction métier remonte.
        """
        func = self._registry.get(method_name)
        if func is None:
            raise KeyError(method_name)
        return func(params)

    def list_methods(self) -> list[str]:
        """Retourne la liste triée des méthodes disponibles."""
        return sorted(self._registry.keys())

    def has_method(self, method_name: str) -> bool:
        """Vérifie si une méthode est enregistrée."""
        return method_name in self._registry
