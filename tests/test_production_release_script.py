from pathlib import Path


SOURCE = Path("scripts/deploy_production.sh").read_text(encoding="utf-8")
COMPOSE = Path("docker-compose.production.yml").read_text(encoding="utf-8")


def test_release_refuses_dirty_tree_and_validates_compose():
    assert "git status --porcelain" in SOURCE
    assert "Refusing production deploy from a dirty Git working tree" in SOURCE
    assert "compose config" in SOURCE


def test_release_takes_backup_before_recreating_application():
    backup = SOURCE.index("backup_postgres.sh")
    build = SOURCE.index("compose build app")
    recreate = SOURCE.index("--force-recreate app")
    assert backup < build < recreate


def test_release_stops_worker_before_app_and_recreates_same_image_afterwards():
    stop_worker = SOURCE.index("compose stop whatsapp-worker")
    recreate_app = SOURCE.index("--force-recreate app")
    recreate_worker = SOURCE.index("--force-recreate whatsapp-worker")
    image_check = SOURCE.index('if [ -z "$app_image" ] || [ "$app_image" != "$worker_image" ]')
    assert stop_worker < recreate_app < recreate_worker < image_check


def test_release_preflights_workflow_before_runtime_cutover_when_required():
    build = SOURCE.index("compose build app")
    workflow_setting = SOURCE.index("settings.N8N_ENABLED")
    workflow_db_start = SOURCE.index('--profile workflow up -d workflow-postgres')
    workflow_db_ready = SOURCE.index("wait_healthy xvond-workflow-postgres")
    workflow_start = SOURCE.index('--profile workflow up -d --no-deps workflow-engine')
    workflow_ready = SOURCE.index("wait_healthy xvond-workflow-engine")
    workflow_probe = SOURCE.index("probe_workflow_contract")
    stop_worker = SOURCE.index("compose stop whatsapp-worker")
    recreate_app = SOURCE.index("--force-recreate app")
    acceptance = SOURCE.index("scripts/production_acceptance.py")
    assert (
        build
        < workflow_setting
        < workflow_db_start
        < workflow_db_ready
        < workflow_start
        < workflow_ready
        < stop_worker
        < recreate_app
        < acceptance
    )
    assert "Workflow contract probe failed" in SOURCE
    assert 'action: "health_check"' in SOURCE
    assert workflow_probe < workflow_db_start
    assert SOURCE.index("    probe_workflow_contract", workflow_ready) < stop_worker


def test_workflow_engine_has_real_http_healthcheck_before_release_continues():
    workflow = COMPOSE.split("  workflow-engine:", 1)[1].split("\nvolumes:", 1)[0]
    assert "healthcheck:" in workflow
    assert "http://127.0.0.1:5678/healthz" in workflow
    assert '"node"' in workflow
    assert "start_period: 30s" in workflow


def test_release_has_mandatory_health_and_optional_customer_acceptance():
    assert "/health/ready" in SOURCE
    assert "ACCEPTANCE_COMPANY_ID" in SOURCE
    assert "scripts/production_acceptance.py" in SOURCE
    assert '"$@" --agent-id' in SOURCE
    assert '"$@" --live-ai' in SOURCE
    assert '"$@" --require-live' in SOURCE
