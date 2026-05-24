def usernames_by_role(conn, role):
    rows = conn.execute(
        f"SELECT username FROM users WHERE role = '{role}' ORDER BY username"
    ).fetchall()
    return [row[0] for row in rows]
