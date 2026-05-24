def load_config(file_config=None, env=None):
    env = env or {}
    config = {"timeout": 30, "endpoint": "http://localhost"}

    if "APP_TIMEOUT" in env:
        config["timeout"] = int(env["APP_TIMEOUT"])
    if file_config:
        config.update(file_config)

    return config
