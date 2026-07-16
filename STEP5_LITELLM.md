# Step 5: LiteLLM Integration

This step implements the LLM Gateway, enabling real LLM calls through LiteLLM with multi-provider support, cost tracking, and intelligent routing.

## What's Implemented

### 1. Model Configuration (src/llm/models.py)
- **Available Models**: GPT-4, GPT-3.5-Turbo, Claude 3 variants
- **Provider Support**: OpenAI, Anthropic, extensible to others
- **Model Routing**: Select best model based on task type
- **Fallback Chains**: Graceful degradation on provider failures
- **Cost Tracking**: Per-model pricing configured

### 2. LLM Gateway (src/llm/gateway.py)
- **Unified Interface**: All LLM calls go through gateway
- **Model Routing**: Automatic model selection based on task
- **Fallback Handling**: Retry with fallback model on failure
- **Async Support**: Full async/await for non-blocking calls
- **Cost Tracking**: Records all usage for billing

### 3. Cost Tracker (src/llm/cost_tracker.py)
- **Usage Recording**: Tracks every LLM call (tokens, model, cost)
- **Cost Calculation**: Accurate cost per request based on model pricing
- **Aggregation**: Get costs by workflow, agent, or model
- **Summary Reports**: Overall cost summary with breakdowns

### 4. Research Agent Integration
Research Agent now:
- Uses **real LLM calls** to generate summaries
- Includes **cost metadata** in output
- Tracks **token usage**
- Supports **fallback models**

### 5. Cost API Endpoints
- `GET /api/workflows/costs/summary` - Overall cost summary
- `GET /api/workflows/{workflow_id}/cost` - Cost for specific workflow

## How It Works

### Model Routing
```python
# Automatic routing based on task type
response = await gateway.generate(
    workflow_id="wf_1",
    agent_id="research_agent",
    prompt="Research AI trends",
    task_type="fast",  # Routes to gpt-3.5-turbo (cheapest)
    max_tokens=500,
)
```

Task Types:
- `"reasoning"` → gpt-4-turbo (complex planning)
- `"coding"` → gpt-4 (code generation)
- `"fast"` → gpt-3.5-turbo (quick/cheap)
- `"default"` → gpt-3.5-turbo

### Cost Tracking
```
Every LLM call:
  1. Records input/output tokens
  2. Calculates cost based on model pricing
  3. Aggregates by workflow/agent/model
  4. Available via API and in agent metadata
```

Example Research Agent output:
```json
{
  "status": "completed",
  "result": {
    "summary": "AI generated summary...",
    ...
  },
  "tokens_used": {
    "input": 150,
    "output": 85,
    "total": 235
  },
  "metadata": {
    "llm_cost": 0.000428,
    "model": "gpt-3.5-turbo"
  }
}
```

## Configuration

### .env
```
OPENAI_API_KEY=sk-proj-...
LITELLM_LOG=TRUE
```

### Switching Models
```python
# Explicit model selection
response = await gateway.generate(
    ...,
    model="gpt-4",  # Use specific model
)

# Capability-based selection
from src.llm.models import get_model_for_capability, ModelCapability
model = get_model_for_capability(ModelCapability.ADVANCED)
```

### Adding New Models
Edit `src/llm/models.py`:
```python
MODELS["my-model"] = ModelConfig(
    name="my-model-official-name",
    provider=Provider.CUSTOM,
    capability=ModelCapability.REASONING,
    input_cost_per_1k_tokens=0.01,
    output_cost_per_1k_tokens=0.05,
    max_input_tokens=4096,
    max_output_tokens=2048,
)
```

## Testing

### Unit Tests
```bash
pytest tests/unit/test_llm_gateway.py -v
```

Tests:
- Model configuration retrieval
- Model routing logic
- Fallback chain
- Cost calculation accuracy
- Cost aggregation (workflow, agent, model)

### Integration Tests
```bash
pytest tests/integration/test_llm_integration.py -v
```

Tests:
- Real LLM calls (requires valid API key)
- Cost tracking during generation
- Research Agent with LLM integration

Note: Integration tests require OPENAI_API_KEY in .env

## Cost Analysis

### Example Workflow
User request: "Research AI trends"

1. **Supervisor Agent**: ~100 tokens → ~$0.00015
2. **Research Agent**: 
   - Web search: No cost
   - LLM summary generation: ~85 output tokens → ~$0.00017

**Total workflow cost**: ~$0.00032 (less than 0.0004 USD)

### Cost by Model (per 1M tokens)
- gpt-3.5-turbo: $2-3
- gpt-4-turbo: $10-30
- gpt-4: $30-60
- Claude 3 Haiku: $2.50
- Claude 3 Opus: $15-75

## Next Steps

**Step 6**: Enhance Tool Gateway
- Add more tools (database, document reader, code executor)
- Advanced permission models
- Tool execution metrics

**Step 9**: LLM-Powered Supervisor
- Use LLM for dynamic task planning
- Replace hardcoded routing rules with learned behavior

## Monitoring

### Check Costs via API
```bash
# Overall summary
curl http://localhost:8000/api/workflows/costs/summary

# Workflow-specific
curl http://localhost:8000/api/workflows/{workflow_id}/cost
```

### View in Logs
Research Agent output includes:
```
tokens_used: {input: X, output: Y}
metadata: {llm_cost: $Z, model: "..."}
```

## Troubleshooting

**"Invalid OpenAI API key"**
- Check .env file has OPENAI_API_KEY
- Key must be valid and active
- Check API key isn't rotated

**"Model not found"**
- Verify model name in MODELS dict
- Check provider is configured
- Review MODEL_ROUTING for task type

**High costs?**
- Switch task_type to "fast" for cheaper model
- Reduce max_tokens limit
- Review cost summary for expensive operations

---

**Step 5 Complete!** Real LLM calls are now working with cost tracking.
Next: Step 6 - Enhanced Tool Gateway.
