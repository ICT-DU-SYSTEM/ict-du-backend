from flask import Flask

app = Flask(__name__)


@app.route("/users", methods=["GET"])
def get_users():
    pass


@app.route("/items/<int:item_id>", methods=["POST"])
def create_item(item_id):
    pass


# Option 1: Print directly in code
for rule in app.url_map.iter_rules():
    methods = ", ".join(rule.methods - {"HEAD", "OPTIONS"})
    print(f"Path: {str(rule):<25} | Endpoint: {rule.endpoint:<15} | Methods: [{methods}]")