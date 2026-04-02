### set up
1. `python -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. create a `.env` file with `OPENAI_API_KEY`

### how to use
**to run full pipeline (extract rules, generate tests, run tests)**
```bash
python -m src.cli.main run-pipeline --agent-dir test_agents/customer_service_agent
```

**to run individual steps**
```bash
python -m src.cli.main extract --agent-dir test_agents/customer_service_agent
```
```bash
python -m src.cli.main generate-tests \
  --extraction-file tests/extraction/customer_service_agent_extraction.yml \
  --entity-schema test_agents/customer_service_agent/entity_schema.yml
```
```bash
python -m src.cli.main run-tests \
  --test-file tests/generation/customer_service_agent_extraction_tests.yml \
  --agent-dir test_agents/customer_service_agent
```

### before contributing
```bash
python -m black .
python -m pylint .
```
