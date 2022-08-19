from app import create_app, cli, errors

app = create_app()
cli.register(app)
errors.register_handler(app)
