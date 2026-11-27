"""An isolated pilot for the indicators handled by the Banxico API connector."""

PILOT_KEYS = ("REMESAS", "RESERVAS", "TASA", "TIPOCAMBIO")


def pilot_selection(keys, available):
    if keys is None:
        return None
    selected = set(keys)
    if not selected or selected - set(PILOT_KEYS) or selected - set(available):
        raise ValueError("Select at least one supported Banxico indicator present in the release")
    return selected
