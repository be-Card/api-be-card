# Reset the entire database, recreate it, and seed it with dummy data.
# Optionally takes `kiosk_id` to map the KIOSK_ID UUID from your test device 
# to the primary test kiosk representation.
reset-app kiosk_id="":
    @echo "Resetting database and destroying volumes..."
    docker-compose down -v
    docker-compose up -d
    @echo "Waiting for DB to initialize..."
    @sleep 10
    @echo "Running migrations..."
    docker-compose exec -T api uv run alembic upgrade head
    @echo "Seeding basic data..."
    docker-compose exec -T api uv run python scripts/simple_seed.py
    @echo "Seeding kiosk and point of sale data..."
    docker-compose exec -T api uv run python scripts/populate_initial_data.py
    @echo "Seeding test tenant..."
    docker-compose exec -T api uv run python scripts/seed_tenant.py
    @echo "Seeding demo cards..."
    docker-compose exec -T api uv run python scripts/seed_demo_cards.py
    @if [ -n "{{kiosk_id}}" ]; then \
        echo "Registering Terminal with ID={{kiosk_id}} and linking to Grifo 1..."; \
        docker-compose exec -T api uv run python scripts/seed_terminal.py "{{kiosk_id}}"; \
    fi
    @echo "Reset complete! API and Database are seeded and ready."
