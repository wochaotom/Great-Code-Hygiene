def can_update(actor, resource):
    if not actor or not resource:
        return False

    if actor.get("role") == "admin":
        return True

    return actor.get("id") == resource.get("owner_id")
