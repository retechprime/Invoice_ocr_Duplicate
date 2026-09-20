# Invoice AI

## Start everything with Docker

```powershell
docker compose up --build
```

Frontend: http://localhost:5173
API: http://localhost:8000/docs
MinIO: http://localhost:9001
RabbitMQ: http://localhost:15673

To run in background:

```powershell
docker compose up --build -d
```

Stop:

```powershell
docker compose down
```

Stop and remove MinIO data:

```powershell
docker compose down -v
```

Set `HF_TOKEN` in `.env` before starting extraction.
