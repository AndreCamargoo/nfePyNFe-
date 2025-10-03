from locust import HttpUser, task, between


class TestUser(HttpUser):
    wait_time = between(1, 3)

    # 👇 Defina o host base da sua API aqui
    host = "http://localhost:8000"  # ou seu domínio se estiver online

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU5NTg3Nzg1LCJpYXQiOjE3NTk1MDEzODUsImp0aSI6IjAwMDBiNGEyNDJhYTQzOGFiMmI2ZWY4MjYzZDM1NTI0IiwidXNlcl9pZCI6MSwidXNlcm5hbWUiOiJhbGxudWJlIiwiZW1haWwiOiJhZG1pbkBhbGxudWJlLmNvbS5iciIsInRpcG9fdXN1YXJpbyI6ImFkbWluIiwiZW1wcmVzYV9pZCI6MSwiaXNfc3RhZmYiOnRydWUsImlzX3N1cGVydXNlciI6dHJ1ZX0.cQ-UW0K9kJ9FpWBkzGNB4CuIfvGBbHElMgcn_DOTYY8"

    def on_start(self):
        self.client.headers.update({
            "Authorization": f"Bearer {self.token}"
        })

    @task
    def get_empresas(self):
        self.client.get("/api/v1/empresas/")

# locust -f app/utils/locustfile.py
# Acesse: http://localhost:8089
